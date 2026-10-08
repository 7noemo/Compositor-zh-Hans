#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""衡量「外挂语言包」方案的真实覆盖上限。

为什么需要单独一个工具：
    extract_strings.py 是「把源码里所有像 UI 文案的字面量都扫出来」，
    分母里混进了大量非本地化位置的字符串（PSD 常量、内部错误消息等），
    用它算出来的覆盖率偏保守，而且不能回答「外挂到底能翻多少」。

    本工具只看**真正的本地化位置**，并把它们分成两类：

      A 类 —— 字面量直接写在本地化位置上，例如
                Text("Add Layer") / .help("Invert") / Label("New", systemImage: "plus")
              SwiftUI 会把它当 LocalizedStringKey，运行时查 Localizable.strings。
              ✅ 外挂语言包**能**翻译这一类。

      B 类 —— 非字面量（变量 / 表达式）出现在同一位置，例如
                Text(title) / .help(help) / Text($0.rawValue)
              SwiftUI 对 String 是按原样渲染的，**不查表**。
              ❌ 外挂语言包翻不了，只有改源码重新编译才行。
              这是外挂方案的能力边界，不是语言包漏了词条。

关于字符串插值（很重要）：
    源码里写 Text("Close \(tab.title)") 时，SwiftUI 运行时查的 key
    **不是** `Close \(tab.title)`，而是把插值换成格式符后的 `Close %@`。
    String 插值 -> `%@`，Int 插值 -> `%lld`。
    所以本工具会把插值字面量「骨架化」（把插值统一成占位符标记）
    再去与语言包的 key 骨架比对，并对类型不确定的插值尝试多种候选
    （`%@` 与 `%lld` 的组合），只要有一种命中就算覆盖。

输出：
    build/coverage.json    机器可读
    stdout                 人类可读报告

用法：
    python3 scripts/tools/analyze_coverage.py <上游源码目录>
    python3 scripts/tools/analyze_coverage.py _upstream --json build/coverage.json
"""
import argparse
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENTRY = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', re.M)

# .strings 里的占位符（含 %1$@ 这类带序号的）
PH_RE = re.compile(
    r'%(?:\d+\$)?[-+ #0]*(?:\d+)?(?:\.\d+)?(?:hh|h|ll|l|q|L|z|j|t)?'
    r'[@diouxXeEfgGaAcsp](?![A-Za-z0-9_])'
)
SKEL = "\x00"   # 骨架里代表「一个占位符 / 一个插值」的标记

VIEW_CALLS = (
    "Text", "Label", "Button", "Menu", "Toggle", "Picker", "Link", "Section",
    "NavigationLink", "SecureField", "TextField", "Tab", "Group", "CommandMenu",
    "CommandGroup", "WindowGroup", "MenuBarExtra", "Sidebar", "ContentUnavailableView",
)
MODIFIERS = (
    "navigationTitle", "navigationSubtitle", "help", "accessibilityLabel",
    "accessibilityHint", "accessibilityValue", "alert", "confirmationDialog",
)
SKIP_DIRS = {"CompositorTests", "CompositorUITests", ".git", ".build", "DerivedData"}

OPENERS = [
    (re.compile(r"(?<![.\w])(?:" + "|".join(VIEW_CALLS) + r")\("), "view"),
    (re.compile(r"\.(?:" + "|".join(MODIFIERS) + r")\("), "modifier"),
]
LIT = re.compile(r'^"(?:[^"\\]|\\.)*"$')

MAX_VARIANTS = 16   # 一条文案最多尝试多少种占位符组合，防止组合爆炸


def unescape(s):
    return (s.replace('\\"', '"').replace('\\n', "\n")
             .replace('\\t', "\t").replace('\\\\', "\\"))


def load_pack(path):
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    return {unescape(m.group(1)): unescape(m.group(2)) for m in ENTRY.finditer(text)}


# ---------------------------------------------------------------- 骨架
def skeleton_of_key(key):
    """语言包 key -> (骨架, [占位符术语...])"""
    phs = PH_RE.findall(key)
    return PH_RE.sub(SKEL, key), phs


def split_interpolations(content):
    """把 Swift 字符串字面量的内容按 \\(...) 切开。

    返回 (骨架, [每个插值的表达式原文])。
    用配平扫描处理 \\\\(Int(a + b)) 这种嵌套。
    """
    parts = []
    args = []
    i = 0
    n = len(content)
    while i < n:
        if content[i] == "\\" and i + 1 < n and content[i + 1] == "(":
            j = i + 2
            depth = 1
            while j < n:
                c = content[j]
                if c == '"':
                    j += 1
                    while j < n:
                        if content[j] == "\\":
                            j += 2
                            continue
                        if content[j] == '"':
                            break
                        j += 1
                    j += 1
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            args.append(content[i + 2:j])
            parts.append(SKEL)
            i = j + 1
            continue
        parts.append(content[i])
        i += 1
    return "".join(parts), args


def guess_types(expr):
    """猜一个插值表达式会生成哪些占位符（返回候选列表，按可能性排序）。

    Swift 的 LocalizedStringKey 规则：
        String 插值 -> %@      Int 插值 -> %lld      Double 插值 -> %lf
    源码里无法 100% 确定类型，所以不确定时返回多个候选 ——
    反正查不到只是「不翻译」，不会出错。
    """
    e = expr.strip()
    if not e:
        return ["%lld"]
    # 明确是整数
    if re.match(r"^(?:Int|UInt|Int8|UInt8|Int16|UInt16|Int32|UInt32|Int64|UInt64)\(", e):
        return ["%lld"]
    if re.search(r"\.(?:count|maximum|minimum|index|maxSide|width|height|pixels)\b", e) and \
       ".formatted(" not in e:
        return ["%lld"]
    if re.search(r"\bInt\b", e) and ".formatted(" not in e:
        return ["%lld"]
    # 明确是字符串
    if (".formatted(" in e or ".description" in e or ".lastPathComponent" in e
            or ".rawValue" in e or ".title" in e or ".name" in e
            or ".label" in e or ".localizedDescription" in e):
        return ["%@"]
    if re.match(r'^"', e):     # 直接是字符串字面量
        return ["%@"]
    # 不确定：两种都试
    return ["%@", "%lld"]


def key_variants(content):
    """给一个字符串字面量内容，生成它可能对应的全部语言包 key。

    纯字面量 -> 只有它自己。
    含插值   -> 骨架 + 各占位符候选的笛卡尔积（上限 MAX_VARIANTS 种）。
    """
    skel, args = split_interpolations(content)
    if not args:
        return [content]
    if SKEL not in skel:
        return [content]
    cands = [guess_types(a) for a in args]
    total = 1
    for c in cands:
        total *= len(c)
    if total > MAX_VARIANTS:
        # 组合太多时只保留「全 %@」与「全 %lld」两种极端写法
        return [skel.replace(SKEL, "%@"), skel.replace(SKEL, "%lld")]
    out = []
    for combo in itertools.product(*cands):
        k = skel
        for ph in combo:
            k = k.replace(SKEL, ph, 1)
        out.append(k)
    return out


# ---------------------------------------------------------------- 扫描
def find_close(t, i):
    depth = 0
    while i < len(t):
        c = t[i]
        if c == '"':
            i += 1
            while i < len(t):
                if t[i] == "\\":
                    i += 2
                    continue
                if t[i] == '"':
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


def first_arg(t, start):
    depth = 0
    i = start
    while i < len(t):
        c = t[i]
        if c == '"':
            i += 1
            while i < len(t):
                if t[i] == "\\":
                    i += 2
                    continue
                if t[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if c in "([":
            depth += 1
        elif c in ")]":
            if depth == 0:
                return t[start:i]
            depth -= 1
        elif c == "," and depth == 0:
            return t[start:i]
        i += 1
    return t[start:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="上游源码目录")
    ap.add_argument("--pack", default=os.path.join(ROOT, "zh-Hans.lproj", "Localizable.strings"))
    ap.add_argument("--json", default="", help="把结果写成 JSON 的路径")
    ap.add_argument("--show-b", type=int, default=15, help="打印多少条 B 类写法")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"❌ 不是目录：{args.src}", file=sys.stderr)
        return 1

    keys = load_pack(args.pack)
    # 骨架 -> 语言包原文（用于反查「这个骨架有没有覆盖」）
    pack_skel = {}
    for k in keys:
        sk, _ = skeleton_of_key(k)
        pack_skel.setdefault(sk, []).append(k)

    a_lit, b_nonlit = {}, {}
    sites = 0
    for dirpath, dirnames, filenames in os.walk(args.src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if not fn.endswith(".swift"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, args.src)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for pat, _kind in OPENERS:
                for m in pat.finditer(text):
                    close = find_close(text, m.end() - 1)
                    if close < 0:
                        continue
                    raw = first_arg(text, m.end()).strip()
                    sites += 1
                    ln = text[: m.start()].count("\n") + 1
                    if LIT.match(raw):
                        content = raw[1:-1]
                        key = unescape(content)
                        a_lit.setdefault(key, []).append(f"{rel}:{ln}")
                    else:
                        b_nonlit.setdefault(raw, []).append(f"{rel}:{ln}")

    # 判定每条 A 类文案是否被覆盖
    covered, missing, covered_via = [], [], {}
    for key in a_lit:
        variants = key_variants(key)
        hit = None
        for v in variants:
            if v in keys:
                hit = v
                break
            sk, _ = skeleton_of_key(v)
            if not hit and sk in pack_skel:
                hit = pack_skel[sk][0]
        if hit:
            covered.append(key)
            if hit != key:
                covered_via[key] = hit
        else:
            missing.append(key)

    pct = round(100.0 * len(covered) / max(1, len(a_lit)), 1)

    report = {
        "source_dir": args.src,
        "localized_sites": sites,
        "translatable": {
            "distinct_strings": len(a_lit),
            "covered": len(covered),
            "missing": len(missing),
            "coverage_percent": pct,
            "note": "字面量直传本地化位置 —— 外挂语言包能翻译的部分",
        },
        "untranslatable": {
            "distinct_expressions": len(b_nonlit),
            "sites": sum(len(v) for v in b_nonlit.values()),
            "note": "变量/表达式进视图 —— SwiftUI 原样渲染不查表，外挂翻不了，需改源码",
        },
        "missing_keys": sorted(missing),
        "matched_via_placeholder_key": {k: v for k, v in sorted(covered_via.items())},
    }

    print(f"源码扫描目录            : {args.src}")
    print(f"语言包                  : {len(keys)} 条")
    print(f"本地化位置调用点        : {sites}")
    print("")
    print(f"A 类（外挂能翻）        : {len(a_lit)} 个不同文案")
    print(f"  已有译文              : {len(covered)}")
    print(f"  缺译文                : {len(missing)}")
    print(f"  => 覆盖率             : {pct}%")
    print("")
    print(f"B 类（外挂翻不了）      : {sum(len(v) for v in b_nonlit.values())} 处"
          f" / {len(b_nonlit)} 种写法")
    print("")
    print(f"其中 {len(covered_via)} 条是靠「插值 -> 格式串」命中的，例如：")
    for k, v in list(sorted(covered_via.items()))[:6]:
        print(f"    源码 {k!r}")
        print(f"    -> 语言包 {v!r}")
    if missing:
        print("")
        print("### A 类里还缺译文的（这些还能靠语言包补上）：")
        for k in sorted(missing)[:40]:
            print(f"    {k!r}")
        if len(missing) > 40:
            print(f"    … 还有 {len(missing) - 40} 个")
    if args.show_b:
        print("")
        print("### B 类里出现最多的写法（这些必须改源码才能翻）：")
        for k in sorted(b_nonlit, key=lambda x: -len(b_nonlit[x]))[:args.show_b]:
            print(f"    ×{len(b_nonlit[k]):2d}  {k[:80]}")

    if args.json:
        d = os.path.dirname(args.json)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\n已写出：{args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
