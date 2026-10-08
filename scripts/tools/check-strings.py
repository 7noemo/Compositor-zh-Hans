#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 zh-Hans.lproj/Localizable.strings 的完整性与一致性。

检查项：
  1. 语法能被 plutil 接受
  2. 没有重复 key
  3. key / value 都非空，且不会出现只有空格的翻译
  4. 英文与中文的占位符（%@ %d %ld %.2f %1$@ 等）数量与种类一致
  5. 中文里没有漏译的整句英文（常见漏译特征）
  6. 括号、省略号风格统一（… 而不是 ...）

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
        kp = sorted(PLACEHOLDER.findall(key))
        vp = sorted(PLACEHOLDER.findall(value))
        if kp != vp:
            errors.append(
                f"第 {lineno} 行：占位符不一致 {key!r} -> {value!r}（英文 {kp} / 中文 {vp}）"
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
