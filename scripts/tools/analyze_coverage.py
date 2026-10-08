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
    用 swiftc 反射 SwiftUI 内部的 key 实测（macOS 27 / Swift 6.4）：

        "Close \(s)"                    -> "Close %@"                 String
        "Current: \(w) × \(h) pixels"   -> "Current: %lld × %lld ..." Int
        "\(d) px"                       -> "%lf px"                   Double

    两条关键结论：
      1. 格式符**永远不带序号** —— 不会出现 "%1$@ × %2$@"。
         所以语言包里的 key 一律不带序号；带序号的 key 是死条目。
         （序号只允许出现在译文里做重排，例如 "%@ of %@." = "%2$@的%1$@。"）
      2. 类型决定格式符：String->%@，Int->%lld，Double->%lf。
         源码里无法 100% 确定类型，所以对不确定的插值会同时给出多种候选。

    本工具的「已覆盖」判定是**精确匹配**：字面量算出的候选 key 必须在语言包里
    逐字符存在（允许语言包一侧是带序号的写法，会自动去掉序号后比）。
    早先用「骨架匹配」（只看占位符位置）会把格式符类型/序号写错的条目
    也判成已覆盖，属于假阳性 —— 那正是「有些文案明明有译文却还显示英文」的根因，
    已废弃。

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


def denum(s):
    """去掉占位符里的序号：%1$@ -> %@。

    SwiftUI 运行时不会生成带序号的 key，但语言包里万一有人写成 %1$@，
    这里自动放行（并在报告里点名），免得把「序号写法」和「真漏翻」混为一谈。
    """
    return re.sub(r"%(\d+)\$", "%", s)


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


INT_TYPES = ("Int", "UInt", "Int8", "UInt8", "Int16", "UInt16",
             "Int32", "UInt32", "Int64", "UInt64")
FLOAT_TYPES = ("Double", "CGFloat", "Float")
INT_PROPS = r"\.(?:count|maximum|minimum|index|maxSide|width|height|pixels)\b"


def guess_types(expr):
    """猜一个插值表达式会生成哪些占位符（候选列表，按可能性排序）。

    Swift 的 LocalizedStringKey 规则：
        String 插值 -> %@      Int 插值 -> %lld      Double 插值 -> %lf

    只有**类型确定**的写法才给单一候选；拿不准就给多候选 ——
    候选多出来只是多几条无害条目，候选少了会造成真漏翻。

    注意别再用 `\\bInt\\b` 这种粗判：`bytes(Int(w), Int(h))` 里含 Int，
    但它返回的是 String（%@），粗判会算成 %lld，把真漏翻掩盖掉。
    """
    e = expr.strip()
    if not e:
        return ["%lld"]
    if re.match(r"^(?:%s)\s*\(" % "|".join(INT_TYPES), e):
        return ["%lld"]
    if re.match(r"^(?:%s)\s*\(" % "|".join(FLOAT_TYPES), e):
        return ["%lf"]
    if ".rounded()" in e:
        return ["%lf"]          # 没被 Int() 包住的取整结果仍是浮点
    if ".formatted(" in e:      # formatted() 返回 String
        return ["%@"]
    if (".description" in e or ".lastPathComponent" in e or ".rawValue" in e
            or ".title" in e or ".name" in e or ".names" in e
            or ".label" in e or ".localizedDescription" in e):
        return ["%@"]
    if re.match(r'^"', e):
        return ["%@"]
    if re.search(INT_PROPS, e) and "(" not in e:
        return ["%lld"]         # 纯属性链，属性名本身就说明是像素/计数
    # 类型判断不了：三种都给，宁可多放几条无害条目，也不漏
    return ["%@", "%lld", "%lf"]


HINTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "key-type-hints.json")
HINTS = {}     # 字面量 -> [每个插值的格式符]，人工核过的真相，优先于 guess_types


def load_hints(path):
    """读插值格式符提示表。读不到就返回空表，退回「猜」。"""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    t = data.get("types") or {}
    return {k: v for k, v in t.items() if isinstance(v, list) and v}


def key_variants(content):
    """给一个字符串字面量内容，生成它可能对应的全部语言包 key。

    纯字面量 -> 只有它自己。
    含插值   -> 优先查提示表（key-type-hints.json，人工核过类型）；
                查不到才按骨架 + 各占位符候选的笛卡尔积生成。
    """
    skel, args = split_interpolations(content)
    if not args:
        return [content]
    if SKEL not in skel:
        return [content]
    h = HINTS.get(content)
    if h and len(h) == len(args):
        k = skel
        for ph in h:
            k = k.replace(SKEL, ph, 1)
        return [k]
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
    ap.add_argument("--hints", default=HINTS_PATH,
                    help="插值格式符提示表（默认 tools/key-type-hints.json）")
    ap.add_argument("--show-b", type=int, default=15, help="打印多少条 B 类写法")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"❌ 不是目录：{args.src}", file=sys.stderr)
        return 1

    HINTS.clear()
    HINTS.update(load_hints(args.hints))

    keys = load_pack(args.pack)
    # 语言包 key 去掉序号后的索引
    pack_denum = {}
    for k in keys:
        pack_denum.setdefault(denum(k), []).append(k)

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

    # 判定每条 A 类文案是否被覆盖 —— 精确匹配，不再做骨架匹配
    covered, missing, covered_via, type_incomplete = [], [], {}, []
    for key in a_lit:
        variants = key_variants(key)
        hits = [v for v in variants if v in keys]
        if not hits:
            hits = [pack_denum[v][0] for v in variants if v in pack_denum]
        if hits:
            covered.append(key)
            if hits[0] != key:
                covered_via[key] = hits[0]
            rest = [v for v in variants if v not in keys and v not in pack_denum]
            if rest:
                type_incomplete.append((key, hits[0], rest))
        else:
            missing.append(key)

    pct = round(100.0 * len(covered) / max(1, len(a_lit)), 1)

    # 提示表健康检查：上游改了文案，这里就会对不上
    stale_hints = sorted(k for k in HINTS if k not in a_lit)
    unhinted = sorted(k for k in a_lit
                      if split_interpolations(k)[1] and k not in HINTS)

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
        "type_incomplete": [
            {"literal": k, "matched": m, "also_consider": r}
            for k, m, r in sorted(type_incomplete)
        ],
        "hints": {
            "loaded": len(HINTS),
            "stale": stale_hints,
            "unhinted_literals": unhinted,
        },
    }

    print(f"源码扫描目录            : {args.src}")
    print(f"语言包                  : {len(keys)} 条")
    print(f"本地化位置调用点        : {sites}")
    print("")
    print(f"A 类（外挂能翻）        : {len(a_lit)} 个不同文案")
    print(f"  已有译文              : {len(covered)}")
    print(f"  缺译文                : {len(missing)}")
    print(f"  => 覆盖率             : {pct}%（精确匹配，非骨架匹配）")
    print("")
    print(f"B 类（外挂翻不了）      : {sum(len(v) for v in b_nonlit.values())} 处"
          f" / {len(b_nonlit)} 种写法")
    print("")
    print(f"其中 {len(covered_via)} 条靠「插值 -> 格式串」命中，例如：")
    for k, v in list(sorted(covered_via.items()))[:6]:
        print(f"    源码 {k!r}")
        print(f"    -> 语言包 {v!r}")
    if type_incomplete:
        print("")
        print(f"### 类型待补齐（{len(type_incomplete)} 条）：源码里看不出插值是 "
              f"String/Int/Double，")
        print("    已命中一种写法，但换成另一种类型就会漏。候选 key 全补上最稳：")
        for k, m, r in sorted(type_incomplete):
            print(f"    {k!r}")
            print(f"        已命中 {m!r}")
            print(f"        可补   {r}")
    if stale_hints:
        print("")
        print(f"⚠️ 提示表里有 {len(stale_hints)} 条已对不上源码（上游改了文案？）：")
        for k in stale_hints[:10]:
            print(f"    {k!r}")
    if unhinted:
        print("")
        print(f"⚠️ 有 {len(unhinted)} 条插值文案还没进提示表（类型靠猜）：")
        for k in unhinted[:10]:
            print(f"    {k!r}")
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
