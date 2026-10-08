#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把上游 Compositor 源码改造成「可完整汉化」的版本。

背景
----
上游界面文案全部硬编码英文，且分两类：

  A 类：字面量直接出现在 SwiftUI 的本地化位置，例如
        Text("Add layer effect") —— SwiftUI 会拿它当 LocalizedStringKey 去查表。
        这一类靠外挂 zh-Hans.lproj 就能汉化。

  B 类：字面量先赋给 String 变量 / 参数，再进视图，例如
        Text(title) / .help(help) / Text(item.message)
        SwiftUI 的 String 重载是「原样渲染」，不查表；字符串插值
        （"Nudge \\(direction) 1 px"）在运行时已经格式化，即便查表也匹配不上。
        这一类永远无法靠外挂语言包汉化 —— 必须改源码。

本脚本做三件事
--------------
  1. 注入运行时查表助手 L()（Compositor/Localized.swift）
  2. 把 B 类中「透传渲染点」的操作数包一层 L()：Text(L(title)) / .help(L(help))
  3. 把 B 类中「带插值的消息」改写成显式格式串：L("Nudge %@ 1 px", direction)

为什么用 L() 而不是 LocalizedStringKey
--------------------------------------
LocalizedStringKey(x) 只做一次查表，插值后的动态内容匹配不上 key；
而 L() 直接用 Bundle 查表，并且：

  * 查不到就原样返回 —— 最坏结果是「没翻译」，绝不会崩或显示错内容
  * 支持显式格式串 + CVarArg，占位符由我们写死，不依赖编译器推断

安全性
------
Rule B 的改动在类型上是恒等的（String -> String），不会引入编译错误；
Rule C 的每条改写都显式写出格式串与参数，占位符一一对应。
脚本幂等，可重复执行；命中数偏离预期时会失败退出，用于在上游重构后及时报警。

用法
----
    python3 localize_patch.py <上游源码根目录> [--repo OWNER/REPO]
"""
import argparse
import os
import re
import sys

# ---------------------------------------------------------------- 助手文件
HELPER_REL = "Compositor/Localized.swift"
HELPER_SRC = '''import Foundation

// 本地化补丁运行时助手（由 Compositor-zh-Hans 注入，勿手工修改）
//
// 上游把大量界面文案先存成 String 再送进视图，SwiftUI 对 String 是原样渲染、
// 不查表，所以那部分文案无法通过外挂语言包汉化。本函数把任意 String 当作
// Localizable.strings 的 key 去查一次：
//
//   * 命中  -> 返回译文
//   * 未命中 -> 原样返回（因此对用户数据、已本地化内容都是安全的）
//
// 带参数的重载用于插值消息：格式串显式写出占位符，避免依赖编译器推断。
func L(_ key: String) -> String {
    guard !key.isEmpty else { return key }
    return Bundle.main.localizedString(forKey: key, value: key, table: nil)
}

func LF(_ format: String, _ args: CVarArg...) -> String {
    guard !format.isEmpty else { return format }
    let resolved = Bundle.main.localizedString(forKey: format, value: format, table: nil)
    return args.isEmpty ? resolved : String(format: resolved, arguments: args)
}
'''

# ------------------------------------------------- Rule B：透传渲染点
#
# 上游把大量界面文案先存成 String 再送进视图，而 SwiftUI 对 String 是「原样渲染、
# 不查表」。要汉化这部分，只能把实参包一层 L()：
#
#     Text(title)                          ->  Text(L(title))
#     .help(help)                          ->  .help(L(help))
#     Text(cond ? "Show Layer" : "Hide")   ->  Text(L(cond ? "Show Layer" : "Hide"))
#     beginEdit("Add Layer")               ->  beginEdit(L("Add Layer"))
#
# 为什么不用一条正则搞定
# ----------------------
# 实参里可能同时出现多个字符串和一个右括号，例如上游真实存在的这一行：
#     .help("Add layer effect").accessibilityLabel("Layer effects")
# 含括号的字符类会把第一个 ) 吃掉，一次 match 就跨到了第二个修饰符上，
# 于是产出 `.help(L("Add layer effect").accessibilityLabel("Layer effects"))` —— 语法崩。
# 所以这里改用「括号配平 + 字符串字面量感知」的扫描，逐个实参处理。
#
# 判定规则（每个实参独立判断）
#   * 简单标识符 title / a.b.c / c[i]  -> 包 L()
#   * 含字符串字面量的表达式（三元、拼接）-> 包 L()
#   * 纯字面量 "..."                -> 也包。收益是查表路径统一，不再依赖
#                                     SwiftUI 的重载解析（LocalizedStringKey vs String：
#                                     两个重载都能接字面量，靠编译器排序决定，不稳）
#   * 含 \( 插值                   -> 跳过。必须走 Rule C 的显式格式串，简单包一层查不到表
#   * 含嵌套括号                   -> 跳过，交给人（宁可漏，不可错）
WRAP_OPENERS = [
    # (正则, 纯字面量是否也包, 名字)
    (re.compile(r'(?<![.\w])(?:Text|Label)\('),       True, "Text"),
    (re.compile(r'\.(?:help|accessibilityLabel|accessibilityHint|accessibilityValue)\('),
     True, "modifier"),
    (re.compile(r'(?<![.\w])beginEdit\('),            True, "beginEdit"),
]

# 形如 "..." 的纯字面量
PURE_LITERAL = re.compile(r'^\s*"(?:[^"\\]|\\.)*"\s*$')
# 简单标识符 / 成员访问 / 下标访问 / 闭包简写参数（$0、$0.rawValue）
#   Text($0.rawValue) 常见于 ForEach { Text($0.rawValue) } 的枚举分段控件，
#   这些 rawValue 正是「像素 / 百分比 / 英寸」这类要翻译的显示值。
SIMPLE_IDENT = re.compile(
    r'^(?:[A-Za-z_][\w.]*|\$\d+(?:\.[A-Za-z_]\w*)*)(?:\[[^\]]+\])?$')

# 用户内容，不能查表（否则用户把图层命名为 "Save" 会被显示成「存储」）
WRAP_EXCLUDE = {
    "tab.title",        # 项目名（用户文件）
    "item.layerName",   # PSD 里的图层名（用户内容）
}


def _find_close(text, open_idx):
    """open_idx 指向 '('，返回配对 ')' 的下标；字符串字面量里的括号不计入。

    找不到配对（跨行/截断）时返回 -1，调用方跳过。
    """
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _expr_ok(arg):
    """实参能不能安全地包一层 L()。"""
    if "\\(" in arg:            # 字符串插值 -> 必须走显式格式串
        return False
    if "//" in arg:             # 行尾注释混进来会切错
        return False
    s = arg.strip()
    if s.startswith("L(") or s.startswith("LF("):
        return False
    # 表达式里已经调用过 L()/LF()（例如 Rule C 刚把插值改写成 LF(...)），
    # 再包一层不仅没意义，还会破坏幂等性。
    if re.search(r'(?<![A-Za-z0-9_.])L(?:F)?\(', arg):
        return False
    return True


def _should_wrap(arg, wrap_pure_literal):
    if _expr_ok(arg) is False:
        return False
    s = arg.strip()
    if not s:
        return False
    if PURE_LITERAL.match(s):
        return wrap_pure_literal
    if SIMPLE_IDENT.match(s):
        return s not in WRAP_EXCLUDE
    if '"' in s:
        return True
    return False


def wrap_line(line, report_skipped, report_excluded, rel):
    """对一行源码做 Rule B 包裹；返回 (新行, 本次包裹数)。

    单行内扫描，跨行的调用原样放过（上游视图代码基本都是一行一处）。
    """
    out, pos, wrapped = [], 0, 0
    while pos < len(line):
        best = None
        for rx, pure, name in WRAP_OPENERS:
            m = rx.search(line, pos)
            if m and (best is None or m.start() < best[0].start()):
                best = (m, pure, name)
        if best is None:
            break
        m, pure, name = best
        open_idx = m.end() - 1                     # 左括号位置
        close = _find_close(line, open_idx)
        if close < 0:
            # 本行没有配对的右括号：跳过这个开头，继续往后找
            out.append(line[pos:open_idx + 1])
            pos = open_idx + 1
            continue
        arg = line[open_idx + 1:close]
        if _should_wrap(arg, pure):
            out.append(line[pos:open_idx + 1])   # 含开括号
            out.append("L(")
            out.append(arg)
            out.append(")")
            out.append(line[close])              # 务必补回原来的右括号
            wrapped += 1
        else:
            out.append(line[pos:close + 1])
            s = arg.strip()
            if s:
                (report_excluded if s in WRAP_EXCLUDE else report_skipped).append(
                    (s[:70], rel))
        pos = close + 1
    out.append(line[pos:])
    return "".join(out), wrapped

# ------------------------------------------------- Rule C：插值消息 -> 显式格式串
# (文件相对路径, 原文, 替换为)
INTERP_RULES = [
    # 撤销 / 重做菜单
    ("Compositor/CompositorApp.swift",
     '"Undo \\(session.history.undoName)"',
     'LF("Undo %@", session.history.undoName)'),
    ("Compositor/CompositorApp.swift",
     '"Redo \\(session.history.redoName)"',
     'LF("Redo %@", session.history.redoName)'),

    # Camera Raw 显隐提示
    ("Compositor/UI/CameraRawControls.swift",
     '"Hide \\(name) in the preview"', 'LF("Hide %@ in the preview", name)'),
    ("Compositor/UI/CameraRawControls.swift",
     '"Show \\(name) in the preview"', 'LF("Show %@ in the preview", name)'),
    ("Compositor/UI/CameraRawControls.swift",
     '"Hide \\(name)"', 'LF("Hide %@", name)'),
    ("Compositor/UI/CameraRawControls.swift",
     '"Show \\(name)"', 'LF("Show %@", name)'),

    # 参数行「双击重置」提示
    ("Compositor/UI/FilterSheet.swift",
     '"\\(title). Double-click to reset."', 'LF("%@. Double-click to reset.", L(title))'),
    ("Compositor/UI/HueSaturationSheet.swift",
     '"\\(title). Double-click to reset."', 'LF("%@. Double-click to reset.", L(title))'),

    # Camera Raw 混色器帮助文本

    # 画布尺寸校验
    ("Compositor/UI/ImageSizeSheet.swift",
     '"Result: \\(Int(width.rounded())) × \\(Int(height.rounded())) pixels"',
     'LF("Result: %lld × %lld pixels", Int(width.rounded()), Int(height.rounded()))'),
    ("Compositor/UI/ImageSizeSheet.swift",
     '"Use 1–\\(DocumentLimits.maxSide.formatted()) pixels per side, up to \\(DocumentLimits.maxSurfaceMegapixels) megapixels, and 1–9,600 pixels/inch."',
     'LF("Use 1–%@ pixels per side, up to %lld megapixels, and 1–9,600 pixels/inch.", '
     'DocumentLimits.maxSide.formatted(), DocumentLimits.maxSurfaceMegapixels)'),
    ("Compositor/UI/NewCanvasSheet.swift",
     '"Enter whole numbers from 1 to \\(DocumentLimits.maxSide.formatted()) pixels."',
     'LF("Enter whole numbers from 1 to %@ pixels.", DocumentLimits.maxSide.formatted())'),
    ("Compositor/UI/NewCanvasSheet.swift",
     '"Enter a size up to \\(DocumentLimits.maxSide.formatted()) pixels at this DPI."',
     'LF("Enter a size up to %@ pixels at this DPI.", DocumentLimits.maxSide.formatted())'),

    # 键盘快捷键面板
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"Opacity digit \\(digit) (type two for exact %)"',
     'LF("Opacity digit %lld (type two for exact %)", digit)'),
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"Nudge \\(direction) 1 px"', 'LF("Nudge %@ 1 px", direction)'),
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"Nudge \\(direction) 10 px"', 'LF("Nudge %@ 10 px", direction)'),
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"Move selected pixels \\(direction) 1 px"', 'LF("Move selected pixels %@ 1 px", direction)'),
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"Move selected pixels \\(direction) 10 px"', 'LF("Move selected pixels %@ 10 px", direction)'),
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"\\(chord.label) is reserved by macOS."', 'LF("%@ is reserved by macOS.", chord.label)'),
    ("Compositor/UI/KeyboardShortcuts.swift",
     '"\\(chord.label) is assigned to both \\(other) and \\(definition.title)."',
     'LF("%@ is assigned to both %@ and %@.", chord.label, other, definition.title)'),

    # 文件大小上限类错误
    ("Compositor/IO/ImageExporter.swift",
     '"Image export supports canvases up to \\(DocumentLimits.maxSurfaceMegapixels) megapixels and \\(DocumentLimits.maxSide.formatted()) pixels per side."',
     'LF("Image export supports canvases up to %lld megapixels and %@ pixels per side.", '
     'DocumentLimits.maxSurfaceMegapixels, DocumentLimits.maxSide.formatted())'),
    ("Compositor/IO/ImageImporter.swift",
     '"This import exceeds the current \\(DocumentLimits.documentBudgetMegapixels)-megapixel document budget or \\(DocumentLimits.maxSide.formatted())-pixel side limit."',
     'LF("This import exceeds the current %lld-megapixel document budget or %@-pixel side limit.", '
     'DocumentLimits.documentBudgetMegapixels, DocumentLimits.maxSide.formatted())'),
    ("Compositor/IO/ProjectStore.swift",
     '"This project exceeds the supported canvas, layer, file-size, or \\(DocumentLimits.documentBudgetMegapixels)-megapixel document limit."',
     'LF("This project exceeds the supported canvas, layer, file-size, or %lld-megapixel document limit.", '
     'DocumentLimits.documentBudgetMegapixels)'),
    ("Compositor/Document/ProjectWorkspace.swift",
     '"The copied layers exceed this project’s \\(DocumentLimits.documentBudgetMegapixels)-megapixel limit."',
     'LF("The copied layers exceed this project’s %lld-megapixel limit.", '
     'DocumentLimits.documentBudgetMegapixels)'),
    ("Compositor/Document/ShapeTool.swift",
     '"That shape is too large. A shape can cover up to \\(DocumentLimits.maxSurfaceMegapixels) megapixels."',
     'LF("That shape is too large. A shape can cover up to %lld megapixels.", '
     'DocumentLimits.maxSurfaceMegapixels)'),
    ("Compositor/Document/TypeTool.swift",
     '"That text box exceeds the \\(DocumentLimits.maxSide.formatted())-pixel or \\(DocumentLimits.maxSurfaceMegapixels)-megapixel limit."',
     'LF("That text box exceeds the %@-pixel or %lld-megapixel limit.", '
     'DocumentLimits.maxSide.formatted(), DocumentLimits.maxSurfaceMegapixels)'),

    # PSD / 字体导入报告
    ("Compositor/IO/PSD/PSDDocumentBuilder.swift",
     '"Folder blend mode “\\(record.blendKey)” isn’t supported. The folder will be pass-through."',
     'LF("Folder blend mode “%@” isn’t supported. The folder will be pass-through.", record.blendKey)'),
    ("Compositor/IO/PSD/PSDDocumentBuilder.swift",
     '"Blend mode “\\(record.blendKey.trimmingCharacters(in: .whitespaces))” isn’t supported and will be applied as Normal."',
     'LF("Blend mode “%@” isn’t supported and will be applied as Normal.", '
     'record.blendKey.trimmingCharacters(in: .whitespaces))'),
    ("Compositor/IO/PSD/PSDText.swift",
     '"The font “\\(name)” isn’t installed, so the text was drawn with the system font."',
     'LF("The font “%@” isn’t installed, so the text was drawn with the system font.", name)'),

    # 撤销动作名（决定「编辑」菜单里 Undo 后面那句话）
    ("Compositor/Document/AdjustmentEditing.swift",
     'beginEdit("Edit \\(original.kind.rawValue) Adjustment")',
     'beginEdit(LF("Edit %@ Adjustment", L(original.kind.rawValue)))'),
    ("Compositor/Document/LayerAdjustment.swift",
     'beginEdit("New \\(kind.rawValue) Adjustment")',
     'beginEdit(LF("New %@ Adjustment", L(kind.rawValue)))'),

    # 画笔/工具的错误提示（弹窗正文）
    ("Compositor/Document/EditorSession+Brush.swift",
     '"“\\(layer.name)” is a folder, which has no pixels of its own. Paint on a layer inside it, or on the folder’s mask."',
     'LF("“%@” is a folder, which has no pixels of its own. Paint on a layer inside it, or on the folder’s mask.", layer.name)'),
    ("Compositor/Document/EditorSession+Brush.swift",
     '"“\\(layer.name)” is hidden, or inside a hidden folder. Show it to paint on it."',
     'LF("“%@” is hidden, or inside a hidden folder. Show it to paint on it.", layer.name)'),
    ("Compositor/Document/EditorSession+Brush.swift",
     '"“\\(layer.name)” is an adjustment layer, with no pixels to paint. Paint on its mask instead."',
     'LF("“%@” is an adjustment layer, with no pixels to paint. Paint on its mask instead.", layer.name)'),

    # 打开 / 保存确认
    ("Compositor/Document/EditorSession.swift",
     '"Open “\\(url.lastPathComponent)”?"',
     'LF("Open “%@”?", url.lastPathComponent)'),
    ("Compositor/IO/ProjectController.swift",
     '"Save changes to \\(session.projectURL?.lastPathComponent ?? "Untitled")?"',
     'LF("Save changes to %@?", session.projectURL?.lastPathComponent ?? "Untitled")'),
    ("Compositor/IO/ProjectController+ExternalChanges.swift",
     '"“\\(session.projectURL?.lastPathComponent ?? "Untitled")” was changed on disk."',
     'LF("“%@” was changed on disk.", session.projectURL?.lastPathComponent ?? "Untitled")'),

    # 图层列表辅助功能 / tooltip
    ("Compositor/UI/NativeLayerList.swift",
     '"Link mask: \\(layer.name)"', 'LF("Link mask: %@", layer.name)'),
    ("Compositor/UI/NativeLayerList.swift",
     '"Unlink mask: \\(layer.name)"', 'LF("Unlink mask: %@", layer.name)'),
    ("Compositor/UI/NativeLayerList.swift",
     '"Clipped to \\(sourceName)"', 'LF("Clipped to %@", sourceName)'),
    ("Compositor/UI/NativeLayerList.swift",
     '"Clipping mask based on \\(sourceName). Option-click the bottom of its row to release."',
     'LF("Clipping mask based on %@. Option-click the bottom of its row to release.", sourceName)'),

    # 项目标签页 / 新建画布
    ("Compositor/UI/ProjectTabLayout.swift",
     '"\\(hiddenCount) more tabs"', 'LF("%lld more tabs", hiddenCount)'),
    ("Compositor/UI/ProjectTabs.swift",
     '"Add to \\(tab.title)"', 'LF("Add to %@", tab.title)'),
    ("Compositor/UI/NewCanvasSheet.swift",
     '"\\(rawValue.capitalized) canvas"', 'LF("%@ canvas", L(rawValue.capitalized))'),
    # ---- 补充批次：同一文案的其它变量名变体 / 遗漏读数 ----
    ("Compositor/UI/NativeLayerList.swift",
     '"Select mask: \\(layer.name)"', 'LF("Select mask: %@", layer.name)'),
    ("Compositor/UI/NativeLayerList.swift",
     '"Clipped to \\(source.name)"', 'LF("Clipped to %@", source.name)'),
    ("Compositor/UI/NativeLayerList.swift",
     '"Clipping mask based on \\(source.name). Option-click the bottom of its row to release."',
     'LF("Clipping mask based on %@. Option-click the bottom of its row to release.", source.name)'),
    ("Compositor/UI/NativeLayerList.swift",
     '"\\(Int(size.width.rounded())) × \\(Int(size.height.rounded())) px"',
     'LF("%lld × %lld px", Int(size.width.rounded()), Int(size.height.rounded()))'),
    ("Compositor/Document/ColorPalette.swift",
     '"Color Picker (\\(kind.rawValue) Color)"',
     'LF("Color Picker (%@ Color)", L(kind.rawValue))'),
    ("Compositor/Document/ColorPalette.swift",
     '"Color Picker (\\(title))"', 'LF("Color Picker (%@)", L(title))'),
    ("Compositor/UI/ColorPickerSheet.swift",
     '"\\(Int(hsb.hue.rounded())) degrees"',
     'LF("%lld degrees", Int(hsb.hue.rounded()))'),
    ("Compositor/UI/NewCanvasSheet.swift",
     '" · \\(Int(resolution)) DPI: \\(w) × \\(h) pixels"',
     'LF(" · %lld DPI: %lld × %lld pixels", Int(resolution), w, h)'),
    # ---- 补充批次 2：图像大小 / 画布大小弹窗读数 ----
    ("Compositor/UI/ImageSizeSheet.swift",
     '"Current: \\(document.width) × \\(document.height) pixels"',
     'LF("Current: %lld × %lld pixels", document.width, document.height)'),
    ("Compositor/UI/CanvasSizeSheet.swift",
     '"Current: \\(draft.originalWidth) × \\(draft.originalHeight) pixels"',
     'LF("Current: %lld × %lld pixels", draft.originalWidth, draft.originalHeight)'),
    ("Compositor/UI/CanvasSizeSheet.swift",
     '"New: \\(Int(draft.width.rounded())) × \\(Int(draft.height.rounded())) pixels · '
     '\\(bytes(Int(draft.width.rounded()), Int(draft.height.rounded()))) uncompressed"',
     'LF("New: %lld × %lld pixels · %@ uncompressed", Int(draft.width.rounded()), '
     'Int(draft.height.rounded()), bytes(Int(draft.width.rounded()), Int(draft.height.rounded())))'),
    ("Compositor/UI/CanvasSizeSheet.swift",
     '"\\(bytes(draft.originalWidth, draft.originalHeight)) uncompressed RGBA canvas"',
     'LF("%@ uncompressed RGBA canvas", bytes(draft.originalWidth, draft.originalHeight))'),
    ("Compositor/UI/CanvasSizeSheet.swift",
     '"Final dimensions must be 1–\\(DocumentLimits.maxSide.formatted()) pixels per side."',
     'LF("Final dimensions must be 1–%@ pixels per side.", DocumentLimits.maxSide.formatted())'),

    # ---- 补充批次 2：Camera Raw / 曲线 / 色阶读数 ----
    ("Compositor/UI/CameraRawColorControls.swift",
     '"In \\(Int((point.x * 255).rounded()))   Out \\(Int((point.y * 255).rounded()))"',
     'LF("In %lld   Out %lld", Int((point.x * 255).rounded()), Int((point.y * 255).rounded()))'),
    ("Compositor/UI/CameraRawColorControls.swift",
     '"Edit \\(CameraRawMixerSettings.names[index])."',
     'LF("Edit %@.", L(CameraRawMixerSettings.names[index]))'),
    ("Compositor/UI/CurvesControls.swift",
     '"Input \\(Int(points[selected].x)) · Output \\(Int(points[selected].y))"',
     'LF("Input %lld · Output %lld", Int(points[selected].x), Int(points[selected].y))'),
    ("Compositor/UI/LevelsSheet.swift",
     '"Original \\(settings.channel.rawValue) histogram"',
     'LF("Original %@ histogram", L(settings.channel.rawValue))'),
    ("Compositor/UI/LevelsSheet.swift",
     '"Click the original layer to set \\(mode.rawValue.lowercased()). '
     'Click the eyedropper again to stop."',
     'LF("Click the original layer to set %@. Click the eyedropper again to stop.", '
     'mode.rawValue.lowercased())'),

    # ---- 补充批次 2：标签页 / 显影 / 套索小工具 ----
    ("Compositor/UI/ProjectTabs.swift",
     '"Close \\(tab.title)"', 'LF("Close %@", tab.title)'),
    ("Compositor/UI/RawDevelopSheet.swift",
     '"Develop “\\(url.lastPathComponent)”"',
     'LF("Develop “%@”", url.lastPathComponent)'),
    ("Compositor/UI/LassoControls.swift",
     '"Enter a whole number from 1 to \\(maximum) px."',
     'LF("Enter a whole number from 1 to %@ px.", maximum.formatted())'),
    ("Compositor/UI/LassoControls.swift",
     'Button(title, action: action)', 'Button(L(title), action: action)'),
    ("Compositor/UI/LassoControls.swift",
     'TextField(title, value: Binding(', 'TextField(L(title), value: Binding('),
    ("Compositor/UI/LassoControls.swift",
     '.help("\\(title) the selection by this many pixels")',
     '.help(LF("%@ the selection by this many pixels", L(title)))'),

    # ---- 补充批次 2：自动命名（未命名 / 组 / 图层）----
    # 这些名字在创建时即被本地化，与 Photoshop 中文版的「未命名-1 / 组 1 / 图层 1」一致。
    # 去重检查用的是同一个 LF()，因此新旧命名能一致地被识别为「已占用」。
    ("Compositor/Document/ProjectWorkspace.swift",
     '"Untitled \\(nextNumber)"', 'LF("Untitled %lld", nextNumber)'),
    ("Compositor/Document/LayerGroups.swift",
     '"Folder \\(number)"', 'LF("Folder %lld", number)'),
    ("Compositor/Document/EditorSession.swift",
     '"Layer \\(number)"', 'LF("Layer %lld", number)'),

    # ---- 补充批次 2：网格设置 ----
    ("Compositor/UI/GridSettingsSheet.swift",
     '"A subdivision every \\(Double(grid.step).formatted('
     '.number.precision(.fractionLength(0...2)))) pixels."',
     'LF("A subdivision every %@ pixels.", Double(grid.step).formatted('
     '.number.precision(.fractionLength(0...2))))'),
    ("Compositor/UI/GridSettingsSheet.swift",
     '"Use gridlines every \\(LayoutGrid.spacingRange.lowerBound)–'
     '\\(LayoutGrid.spacingRange.upperBound.formatted()) pixels and '
     '\\(LayoutGrid.subdivisionRange.lowerBound)–\\(LayoutGrid.subdivisionRange.upperBound) '
     'subdivisions, no more than the pixels between gridlines."',
     'LF("Use gridlines every %lld–%@ pixels and %lld–%lld subdivisions, '
     'no more than the pixels between gridlines.", LayoutGrid.spacingRange.lowerBound, '
     'LayoutGrid.spacingRange.upperBound.formatted(), LayoutGrid.subdivisionRange.lowerBound, '
     'LayoutGrid.subdivisionRange.upperBound)'),

    # ---- 补充批次 2：JPEG 导出 ----
    # 注意 100%% —— 这句会走 String(format:)，裸 % 会被当成转换符，必须写成 %%
    ("Compositor/UI/JPEGExportSheet.swift",
     '"Zoom in (⌘+), now \\(percent). At 100% each pixel of the JPEG is one pixel of '
     'the screen, as on the canvas"',
     'LF("Zoom in (⌘+), now %@. At 100%% each pixel of the JPEG is one pixel of '
     'the screen, as on the canvas", percent)'),
    ("Compositor/UI/JPEGExportSheet.swift",
     '"Zoom out (⌘−), now \\(percent)"',
     'LF("Zoom out (⌘−), now %@", percent)'),
    ("Compositor/UI/JPEGExportSheet.swift",
     '"\\(raster.image.width.formatted()) × \\(raster.image.height.formatted()) px · sRGB"',
     'LF("%@ × %@ px · sRGB", raster.image.width.formatted(), raster.image.height.formatted())'),

    # ---- 补充批次 2：工程格式版本 ----
    ("Compositor/IO/ProjectStore.swift",
     '"This project uses format version \\(version). This app supports versions '
     '\\(ProjectManifest.supported.lowerBound)–\\(ProjectManifest.supported.upperBound)."',
     'LF("This project uses format version %lld. This app supports versions %lld–%lld.", '
     'version, ProjectManifest.supported.lowerBound, ProjectManifest.supported.upperBound)'),
    # ---- 补充批次 3：字符串拼接型的操作名（撤销菜单会显示这些）----
    ("Compositor/Document/LayerEffects.swift",
     '"Add " + kind.rawValue', 'LF("Add %@", L(kind.rawValue))'),
    ("Compositor/Document/LayerEffects.swift",
     '"Cancel " + editing.kind.rawValue', 'LF("Cancel %@", L(editing.kind.rawValue))'),
    ("Compositor/Document/LayerEffects.swift",
     '"Edit " + editing.kind.rawValue', 'LF("Edit %@", L(editing.kind.rawValue))'),
    ("Compositor/Document/LayerEffects.swift",
     '"Copy " + kind.rawValue', 'LF("Copy %@", L(kind.rawValue))'),
    ("Compositor/Document/LayerEffects.swift",
     '(enabled ? "Hide " : "Show ") + kind.rawValue',
     '(enabled ? LF("Hide %@", L(kind.rawValue)) : LF("Show %@", L(kind.rawValue)))'),
    ("Compositor/Document/LayerEffects.swift",
     '"Remove " + selectedEffect.kind.rawValue',
     'LF("Remove %@", L(selectedEffect.kind.rawValue))'),
    ("Compositor/UI/NativeLayerList.swift",
     '(enabled ? "Hide " : "Show ") + kind.rawValue',
     '(enabled ? LF("Hide %@", L(kind.rawValue)) : LF("Show %@", L(kind.rawValue)))'),
    ("Compositor/UI/NativeLayerList.swift",
     '"Click to select; double-click to edit; Option-drag to copy " + kind.rawValue.lowercased()',
     'LF("Click to select; double-click to edit; Option-drag to copy %@", '
     'L(kind.rawValue.lowercased()))'),
    ("Compositor/UI/TypeControls.swift",
     '"Align " + alignment.rawValue.lowercased()',
     'LF("Align %@", L(alignment.rawValue.lowercased()))'),

    # ---- 补充批次 3：删除菜单（整条三元表达式包 L()）----
    # 拆成两步会很难维护：这里一次替换整段，占位符与用户数据都用 L() 包好。
    ("Compositor/CompositorApp.swift",
     'Button(session.selectedEffect != nil ? "Delete " + session.selectedEffect!.kind.rawValue'
     ' : session.isMaskSelected && session.activeLayer?.mask != nil ? "Delete Layer Mask"'
     ' : session.selectedLayerIDs.count > 1 ? "Delete Layers" : "Delete Layer")',
     'Button(L(session.selectedEffect != nil ? LF("Delete %@", '
     'L(session.selectedEffect!.kind.rawValue))'
     ' : session.isMaskSelected && session.activeLayer?.mask != nil ? "Delete Layer Mask"'
     ' : session.selectedLayerIDs.count > 1 ? "Delete Layers" : "Delete Layer"))'),

    # ---- 补充批次 3：AppKit 侧直接赋值的文案 ----
    ("Compositor/Document/LiveLayerMask.swift",
     'ids.count == 1 ? "This layer supplies a live mask" : "These layers supply live masks"',
     'L(ids.count == 1 ? "This layer supplies a live mask" : "These layers supply live masks")'),
    ("Compositor/IO/ProjectController.swift",
     'asNew ? "Save Project As" : "Save Project"',
     'L(asNew ? "Save Project As" : "Save Project")'),
    # ---- 补充批次 4：图层自动命名的另一处（选区浮层）----
    ("Compositor/Document/SelectionClipboard.swift",
     '"Layer \\(number)"', 'LF("Layer %lld", number)'),

    # ---- 补充批次 4：工具头部的整段操作提示 ----
    # 这条三元表达式有 15 个分支、700 多字符，且其中一个分支里还有字符串插值，
    # 所以 Rule B 不敢碰（含 \( ），Rule C 的单条规则也包不住。
    # 这里用「首尾两个锚点各改一次」的办法，把整条表达式包进 L()：
    #   ① 头：Text(  ->  Text(L(
    #   ② 尾：...)")  ->  ...)"))
    #   ③ 顺带把唯一那处插值改写成显式格式串
    # 两个锚点都在文件里唯一，上游一旦改动这里，本脚本会立刻报「未命中」。
    ("Compositor/ContentView.swift",
     'Text(session.tool == .marquee ? (session.marqueeKind == .ellipse ?',
     'Text(L(session.tool == .marquee ? (session.marqueeKind == .ellipse ?'),
    ("Compositor/ContentView.swift",
     '"Drag to draw a shape on a new layer · Shift \\(session.shapeKind == .line ? "45°" '
     ': session.shapeKind == .rectangle ? "square" : "circle") · Option from center '
     '· Shift-U or Tab for the next shape · Escape cancel · Space to pan"',
     'LF("Drag to draw a shape on a new layer · Shift %@ · Option from center '
     '· Shift-U or Tab for the next shape · Escape cancel · Space to pan", '
     'session.shapeKind == .line ? "45°" '
     ': session.shapeKind == .rectangle ? "square" : "circle")'),
    ("Compositor/ContentView.swift",
     '"Click to zoom in · Option-click to zoom out · Drag right or left to zoom smoothly '
     '· Space to pan")',
     '"Click to zoom in · Option-click to zoom out · Drag right or left to zoom smoothly '
     '· Space to pan"))'),
]

# ------------------------------------------------- Rule D-2：Camera Raw 显隐按钮的名称
# eye(shown:name:group:) 的 name 是 String，会进 "Hide %@"/"Show %@"。
# 若不在传参处本地化，会渲染出「隐藏 Light」这种中英混杂。
NAME_ARG = re.compile(r'(?<![A-Za-z])name: "(?P<lit>[^"\\]+)"')
NAME_ARG_FILES = {"Compositor/UI/CameraRawControls.swift"}

# 补丁后统计用：凡是已经带上 L() 的渲染点
TOTAL_WRAPPED = re.compile(
    r'(?<![.\w])(?:Text|Label)\(L\(|'
    r'\.(?:help|accessibilityLabel|accessibilityHint|accessibilityValue)\(L\(|'
    r'(?<![.\w])beginEdit\(L\(')

# 健康检查阈值：补丁后应至少有这么多个渲染点带 L()。
# 数字来自 v1.4.6 的实测值（365），留出余量后取 300。
# 上游若重构视图层导致大幅下降，说明 Rule B 的锚点需要跟着调整。
MIN_WRAPPED = 300

# ------------------------------------------------- Rule E：Sparkle 更新链路
# 更新源不是常量，而是运行时用 --repo 拼出来的（见下面 Rule E 的实现：
# "https://raw.githubusercontent.com/%s/main/appcast.xml" % args.repo）。
# 这里原先放过一个 APPCAST_PLACEHOLDER 常量 —— 它既没被任何代码引用，
# 又会给 scripts/set-repo.sh 的全局替换多制造一个「看起来像配置、其实是死值」
# 的位置（被替换成某个具体仓库后更容易误以为它在起作用），已删除。


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="上游源码根目录")
    ap.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="你的 GitHub 仓库，形如 OWNER/REPO（必填：用来改写 Sparkle 更新源"
             "与「检查更新」菜单，留空会把更新指向别人的仓库）",
    )
    args = ap.parse_args()

    if not args.repo:
        print("❌ 缺少 --repo OWNER/REPO。它会写进 Info.plist 的 SUFeedURL 与"
              "「检查更新」菜单，不能猜。", file=sys.stderr)
        return 2

    root = os.path.abspath(args.src)
    if not os.path.isdir(os.path.join(root, "Compositor")):
        print(f"❌ 看起来不是 Compositor 源码目录：{root}", file=sys.stderr)
        return 1

    report = {}

    # ---------- 1. 注入助手 ----------
    helper_path = os.path.join(root, HELPER_REL)
    os.makedirs(os.path.dirname(helper_path), exist_ok=True)
    existing = read(helper_path) if os.path.exists(helper_path) else None
    if existing != HELPER_SRC:
        write(helper_path, HELPER_SRC)
    report["helper"] = HELPER_REL

    # ---------- 2. 包裹透传渲染点 + 撤销栈操作名（Rule B / B-2 / D 合一）----------
    wrapped = 0
    skipped = []
    excluded = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "Compositor")):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".build"}]
        for fn in filenames:
            if not fn.endswith(".swift"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            lines = read(p).split("\n")
            before = wrapped
            for i, line in enumerate(lines):
                new_line, n = wrap_line(line, skipped, excluded, rel)
                if n:
                    lines[i] = new_line
                    wrapped += n
            if wrapped != before:
                write(p, "\n".join(lines))
    report["wrapped_render_sites"] = wrapped
    report["skipped_user_content"] = excluded
    report["skipped_unwrappable"] = skipped

    # ---------- 3. 插值消息 ----------
    applied, missed = 0, []
    for rel, old, new in INTERP_RULES:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            missed.append((rel, old, "文件不存在"))
            continue
        text = read(p)
        if new in text:            # 幂等
            applied += 1
            continue
        if text.count(old) == 0:
            missed.append((rel, old, "未找到原文"))
            continue
        text = text.replace(old, new)
        write(p, text)
        applied += 1
    report["interp_rules_applied"] = applied
    report["interp_rules_missed"] = missed

    # ---------- 4. Camera Raw 显隐按钮的 name 实参 ----------
    n_name = 0
    for rel in NAME_ARG_FILES:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue
        text = read(p)
        new_text, n = NAME_ARG.subn(
            lambda m: f'name: L("{m.group("lit")}")'
            if not m.group(0).startswith("name: L(") else m.group(0),
            text)
        if n:
            write(p, new_text)
            n_name += n
    report["name_args"] = n_name

    # 统计补丁后「实际带着 L() 的渲染点」总数（跨重跑稳定，用它做健康检查）
    total_wrapped = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "Compositor")):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".build"}]
        for fn in filenames:
            if not fn.endswith(".swift"):
                continue
            t = read(os.path.join(dirpath, fn))
            total_wrapped += len(TOTAL_WRAPPED.findall(t))
    report["total_wrapped_after"] = total_wrapped

    # ---------- 5. Sparkle：切断回退英文版的通道 ----------
    plist = os.path.join(root, "Config/Info.plist")
    if os.path.exists(plist):
        t = read(plist)
        t = re.sub(r'(<key>SUEnableAutomaticChecks</key>\s*)<true/>', r'\1<false/>', t)
        if "<key>SUAutomaticallyUpdate</key>" not in t:
            t = t.replace(
                "<key>SUEnableAutomaticChecks</key>",
                "<key>SUAutomaticallyUpdate</key>\n\t<false/>\n\t<key>SUEnableAutomaticChecks</key>")
        feed = "https://raw.githubusercontent.com/%s/main/appcast.xml" % args.repo
        t = re.sub(
            r'(<key>SUFeedURL</key>\s*)<string>[^<]*</string>',
            lambda m: m.group(1) + f"<string>{feed}</string>", t)
        write(plist, t)
        report["sparkle_feed"] = feed

    # 「检查更新」菜单改为打开本仓库 Releases，避免让 Sparkle 去够官方源
    app_swift = os.path.join(root, "Compositor/CompositorApp.swift")
    if os.path.exists(app_swift):
        t = read(app_swift)
        old_btn = 'Button("Check for Updates…") { applicationDelegate.updater.checkForUpdates(nil) }'
        new_btn = ('Button("Check for Updates…") {\n'
                   '                            NSWorkspace.shared.open('
                   f'URL(string: "https://github.com/{args.repo}/releases")!)\n'
                   '                        }')
        if old_btn in t:
            write(app_swift, t.replace(old_btn, new_btn))
            report["check_updates_menu"] = "改为打开本仓库 Releases"
        else:
            report["check_updates_menu"] = "未找到原文（上游可能已改动）"

    # ---------- 报告 ----------
    print("=" * 62)
    print("本地化补丁报告")
    print("=" * 62)
    print(f"  注入助手文件            : {report['helper']}")
    print(f"  本次新包裹渲染点        : {report['wrapped_render_sites']}")
    print(f"  补丁后带 L() 的渲染点   : {report['total_wrapped_after']}"
          f"  (预期 ≥ {MIN_WRAPPED})")
    if report["skipped_user_content"]:
        print(f"  刻意跳过的用户内容       : {len(report['skipped_user_content'])}")
        for a, f in report["skipped_user_content"]:
            print(f"      {a}  ({f})")
    if report["skipped_unwrappable"]:
        print(f"  跳过的复杂/插值实参      : {len(report['skipped_unwrappable'])}"
              "（插值类另有 Rule C 兜底）")
        for a, f in report["skipped_unwrappable"][:12]:
            print(f"      {a}  ({f})")
        if len(report["skipped_unwrappable"]) > 12:
            print(f"      … 其余 {len(report['skipped_unwrappable']) - 12} 条从略")
    print(f"  插值消息改写            : {report['interp_rules_applied']}/{len(INTERP_RULES)}")
    print(f"  本次新包裹 Camera Raw 名称: {report['name_args']}")
    print(f"  Sparkle 更新源           : {report.get('sparkle_feed', '(未处理)')}")
    print(f"  检查更新菜单            : {report.get('check_updates_menu', '(未处理)')}")

    ok = True
    if report["interp_rules_missed"]:
        ok = False
        print()
        print("❌ 以下插值规则未命中（上游改了写法，需要同步更新本脚本）：")
        for rel, old, why in report["interp_rules_missed"]:
            print(f"   [{why}] {rel}")
            print(f"        {old}")
    if report["total_wrapped_after"] < MIN_WRAPPED:
        ok = False
        print()
        print(f"⚠️  补丁后只有 {report['total_wrapped_after']} 个渲染点带 L()"
              f"（预期 ≥ {MIN_WRAPPED}），上游可能重构过视图层，请人工复核。")

    print()
    print("✅ 补丁应用完成" if ok else "⚠️  补丁应用完成，但有告警（见上）")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
