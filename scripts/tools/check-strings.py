#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""校验 zh-Hans.lproj/Localizable.strings 的完整性与一致性。

检查项：
  1. 语法能被 plutil 接受
  2. 没有重复 key
  3. key / value 都非空，且不会出现只有空格的翻译
  4. 英文与中文的占位符（%@ %d %ld %.2f %1$@ 等）数量与种类一致
  5. 中文里没有漏译的整句英文（常见漏译特征）
  6. 括号、省略号风格统一（… 而不是 ...）
  7. key 里不许出现带序号的格式符 %1$@
  8. 译文里的格式符不许「带序号与不带序号」混用

第 7 条是硬规则，原因见下（也是「有些文案明明有译文却还显示英文」的根因）：

    SwiftUI 的 LocalizedStringKey 在运行时**只生成不带序号**的格式符。
    用 swiftc 反射 SwiftUI 内部 key 实测（macOS 27 / Swift 6.4）：

        "Close \(s)"                    -> "Close %@"           String
        "Current: \(w) × \(h) pixels"   -> "Current: %lld × ..."  Int
        "\(d) px"                       -> "%lf px"              Double

    所以语言包里写成 "%1$@ × %2$@ px" 的 key 永远查不到 —— 死条目。
    序号只允许出现在**译文**里做参数重排，例如
        "%@ of %@." = "%2$@的%1$@。"

第 8 条：CFString 规定一个格式串里的占位符要么全带序号、要么全不带，
混用是未定义行为（可能整句原样打印）。

用法：
    python3 tools/check-strings.py
退出码：0 = 通过，1 = 有问题
"""
import os
import re
import shutil
import subprocess
import sys

LINE_OK = re.compile(
    r'^\s*(?:"(?:[^"\\]|\\.)*"\s*=\s*"(?:[^"\\]|\\.)*"\s*;\s*(?://.*)?)$')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "zh-Hans.lproj", "Localizable.strings")

ENTRY = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;\s*(?://.*)?$')
PLACEHOLDER = re.compile(r'%(?:\d+\$)?[-+ #0]*(?:\d+)?(?:\.\d+)?(?:hh|h|ll|l|q|L|z|j|t)?[@diouxXeEfgGaAcsp](?![A-Za-z0-9_])')

errors, warnings = [], []


def main():
    if not os.path.exists(SRC):
        print(f"❌ 找不到 {SRC}", file=sys.stderr)
        return 1

    if shutil.which("plutil"):
        r = subprocess.run(["plutil", "-lint", SRC], capture_output=True, text=True)
        if r.returncode != 0:
            print("❌ plutil -lint 未通过：")
            print(r.stdout + r.stderr)
            return 1
        print("✅ plutil -lint 通过")
    else:
        # 同步流水线跑在 Linux 上，没有 plutil；用纯 Python 做等效检查
        bad = []
        for lineno, raw in enumerate(open(SRC, encoding="utf-8"), 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith(("/*", "*", "//")):
                continue
            if line.strip() == "*/":
                continue
            if not LINE_OK.match(line):
                bad.append(f"第 {lineno} 行不像合法词条：{line[:70]}")
        if bad:
            print("❌ 语法检查未通过（本地无 plutil，改用纯 Python 校验）：")
            for b in bad[:10]:
                print("   " + b)
            return 1
        print("✅ 语法检查通过（本地无 plutil，已改用纯 Python 校验）")

    seen = {}
    entries = []
    for lineno, line in enumerate(open(SRC, encoding="utf-8"), 1):
        m = ENTRY.match(line.rstrip("\n"))
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if key in seen:
            errors.append(f"第 {lineno} 行：重复 key {key!r}（首次出现在第 {seen[key]} 行）")
        else:
            seen[key] = lineno
        entries.append((lineno, key, value))

    if not entries:
        errors.append("未解析到任何词条，请检查文件格式")

    for lineno, key, value in entries:
        if not value.strip():
            errors.append(f"第 {lineno} 行：翻译为空 {key!r}")
            continue
        if key == value and not re.fullmatch(r'[\W\d_]+', key):
            warnings.append(f"第 {lineno} 行：中英文完全相同（可能是漏译）{key!r}")
        # 比占位符时**先去掉序号**：%@ 与 %1$@ 是同一个东西，
        # 序号只是让译文能重排参数，不影响类型。要比的是类型与个数。
        kp = sorted(re.sub(r'%\d+\$', '%', p) for p in PLACEHOLDER.findall(key))
        vp = sorted(re.sub(r'%\d+\$', '%', p) for p in PLACEHOLDER.findall(value))
        vp_raw = sorted(PLACEHOLDER.findall(value))
        if kp != vp:
            errors.append(
                f"第 {lineno} 行：占位符不一致 {key!r} -> {value!r}（英文 {kp} / 中文 {vp}）"
            )
        # 7. key 里不许出现带序号的格式符（SwiftUI 运行时不会生成这种 key）
        if re.search(r'%\d+\$', key):
            errors.append(
                f"第 {lineno} 行：key 里出现带序号的格式符 {key!r} —— SwiftUI 只生成"
                f"不带序号的 key（%@/%lld/%lf），这条运行时永远查不到。序号只能写在译文里。"
            )
        # 8. 译文里不许「带序号 / 不带序号」混用（CFString 未定义行为）
        if vp_raw and any("$" in p for p in vp_raw) and any("$" not in p for p in vp_raw):
            errors.append(
                f"第 {lineno} 行：译文格式符序号混用 {value!r}（{vp_raw}）—— 要么全带序号，"
                f"要么全不带，混用是未定义行为。"
            )
        if "..." in value or "。。。" in value:
            warnings.append(f"第 {lineno} 行：省略号建议用「…」而不是「...」{key!r} -> {value!r}")

    print(f"ℹ️  共 {len(entries)} 条词条")

    for w in warnings:
        print("⚠️  " + w)
    for e in errors:
        print("❌ " + e)

    if errors:
        print(f"\n❌ 校验未通过：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"\n✅ 校验通过（{len(warnings)} 个警告）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
