#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从上游源码里提取全部「人可读」的界面字符串字面量，与现有语言包比对。

与社区版 extract-missing.py 的区别：
  * 不限定调用点，而是全量扫字面量后按特征过滤 —— 因为打上本地化补丁后，
    原本「藏在 String 参数里」的文案（组件调用点的实参、数组/枚举里的文案）
    同样会开始走查表，只扫本地化调用点会大面积漏掉。
  * 额外排除 Swift 标识符、PSD 格式常量、SF Symbol 名等噪音。

输出：
  build/to-translate.tsv   待译词条（key <TAB> 来源位置），人工/AI 填第二列
  build/already-covered.txt 已在语言包中的
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用「插值 -> 格式串」的骨架匹配逻辑，避免把 Close \(tab.title) 这种
# 明明已经译好的文案误报成待翻译（它在语言包里存的是 Close %@）。
from analyze_coverage import key_variants, skeleton_of_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PACK = os.path.join(ROOT, "zh-Hans.lproj", "Localizable.strings")
OUT_DIR = os.path.join(ROOT, "build")

LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"')
SKIP_DIRS = {"CompositorTests", "CompositorUITests", ".git", ".build", "DerivedData"}

# ---- 噪音判定 -------------------------------------------------------------
# PSD / TIFF 格式常量（8BIM、Lr16、TySh…）
PSD_CONST = re.compile(r'^(?:8BIM|8BPS|8B64|[A-Z][a-z]?\d{2}|[A-Z]{1,2}[a-z]{2,3})$')
SWIFT_ID = re.compile(r'^[a-z][A-Za-z0-9]*$|^[A-Z][A-Za-z0-9]*$|^[a-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)+$')
FILEISH = re.compile(
    r'\.(swift|png|jpg|jpeg|json|plist|xml|comp|txt|strings|tiff|heic|dmg|mask\.png)$'
    r'|^https?:|^com\.')
FORMAT_ONLY = re.compile(r'^[%\d.\-–—×\s°]+$|^%[@dlsf]|^\\[nrt]')
# 代码/SwiftUI 关键字、选择器、IB 标识
CODEISH = re.compile(
    r':$|^_NS|^NS[A-Z]|^CG[A-Z]|^CI[A-Z]|^UTType|^k[A-Z]|^XCTest|^__|^ToolbarItem'
    r'|^accessibility|^userActivity|^com\.apple')
# 只有一个词且短、又没有空格的，多半是标识符或单位（后续单独人工甄别）
SHORT_TOKEN = re.compile(r'^[A-Za-z][A-Za-z0-9/+.\-]*$')


def unescape(s):
    return (s.replace('\\"', '"').replace('\\n', "\n").replace('\\t', "\t")
             .replace('\\\\', "\\"))


def load_pack(path):
    """读 .strings 成 dict。

    刻意用纯 Python 解析而不是 plutil：同步流水线跑在 Linux runner 上，
    没有 plutil 可用；而且我们只需要 key，不需要完整的 plist 语义。
    """
    text = open(path, encoding="utf-8-sig").read()
    out = {}
    for m in ENTRY.finditer(text):
        out[unescape(m.group(1))] = unescape(m.group(2))
    return out


ENTRY = re.compile(
    r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', re.M)


def strip_comments(text):
    """去掉注释，但要小心别把字符串里的 // 当成注释。

    之前用 line.split("//", 1) 一刀切，会把
        let u = "https://example.com/x"
    变成
        let u = "https:
    —— 引号从此不配平，后面所有行扫出来的字面量都是错的。
    """
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    out = []
    for line in text.split("\n"):
        i = 0
        n = len(line)
        cut = n
        while i < n:
            c = line[i]
            if c == '"':
                i += 1
                while i < n:
                    if line[i] == "\\":
                        i += 2
                        continue
                    if line[i] == '"':
                        break
                    i += 1
                i += 1
                continue
            if c == "/" and i + 1 < n and line[i + 1] == "/":
                cut = i
                break
            i += 1
        out.append(line[:cut])
    return "\n".join(out)


def is_noise(s):
    if len(s.strip()) < 2:
        return True
    if not re.search(r"[A-Za-z]", s):
        return True
    if s in {"true", "false", "nil", "self"}:
        return True
    if PSD_CONST.match(s) and not " " in s:
        return True
    if FILEISH.search(s):
        return True
    if FORMAT_ONLY.match(s):
        return True
    if CODEISH.search(s):
        return True
    if len(s) > 400:
        return True
    return False


def is_maybe_ui(s):
    """看起来像给人看的文案：含空格、或首字母大写后跟小写、或以大写字母开头。"""
    if " " in s:
        return True
    if re.match(r"^[A-Z][a-z]", s):
        return True
    if re.match(r"^[A-Z][A-Za-z]*[/\-][A-Za-z]", s):   # Hue/Saturation、Black & White
        return True
    return False


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_upstream")
    pack_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PACK
    if not os.path.isdir(src):
        print(f"❌ 不是目录：{src}", file=sys.stderr)
        return 1

    pack = load_pack(pack_path)
    keys = set(pack)
    # 骨架索引：把语言包 key 里的占位符统一成标记，
    # 这样 「Close %@」 与源码里的 「Close \(tab.title)」 能对上。
    pack_skel = {}
    for k in keys:
        sk, _ = skeleton_of_key(k)
        pack_skel.setdefault(sk, []).append(k)

    def covered_by(lit):
        """返回命中的语言包 key（可能是插值对应的格式串），没命中返回 None。"""
        for v in key_variants(lit):
            if v in keys:
                return v
            sk, _ = skeleton_of_key(v)
            if sk in pack_skel:
                return pack_skel[sk][0]
        return None

    found = {}   # literal -> first 位置
    tokens = {}  # 单词型候选
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if not fn.endswith(".swift"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, src)
            try:
                txt = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for lineno, line in enumerate(strip_comments(txt).split("\n"), 1):
                for lit in LITERAL.findall(line):
                    lit = lit.replace('\\"', '"')
                    if is_noise(lit):
                        continue
                    if is_maybe_ui(lit):
                        found.setdefault(lit, f"{rel}:{lineno}")
                    elif SHORT_TOKEN.match(lit) and lit not in keys:
                        tokens.setdefault(lit, f"{rel}:{lineno}")

    todo = {}
    covered = []
    for k, where in found.items():
        if covered_by(k):
            covered.append(k)
        else:
            # 待翻译列表里给出「语言包应该加的 key 形式」：
            # 插值文案要写成 Close %@，而不是 Close \(tab.title)。
            todo[key_variants(k)[0]] = where

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "to-translate.tsv"), "w", encoding="utf-8") as fh:
        fh.write("# key\t译文\t来源\n")
        for k in sorted(todo):
            fh.write(f"{k}\t\t{todo[k]}\n")
    with open(os.path.join(OUT_DIR, "single-token-candidates.txt"), "w", encoding="utf-8") as fh:
        for k in sorted(tokens):
            fh.write(f"{k}\t{tokens[k]}\n")

    pct = round(100.0 * len(covered) / max(1, len(found)), 1)
    # 给 CI 与 README 用的机器可读统计
    with open(os.path.join(OUT_DIR, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "source_dir": os.path.relpath(src, ROOT) if src.startswith(ROOT) else src,
            "pack_path": os.path.relpath(pack_path, ROOT) if pack_path.startswith(ROOT) else pack_path,
            "strings_total": len(keys),
            "found": len(found),
            "covered": len(covered),
            "todo": len(todo),
            "single_tokens": len(tokens),
            "coverage_percent": pct,
        }, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"源码扫描目录          : {src}")
    print(f"语言包                : {len(keys)} 条")
    print(f"扫到疑似 UI 文案      : {len(found)}")
    print(f"  其中已在语言包        : {len(covered)}")
    print(f"❗ 待翻译（含空格/短语）: {len(todo)}   -> build/to-translate.tsv")
    print(f"❔ 单词型待甄别        : {len(tokens)}   -> build/single-token-candidates.txt")
    print()
    print("覆盖率: %.1f%%" % pct)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
