#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 build/coverage.json，判断还有没有「带实际内容」的 A 类缺口。

为什么不用百分比阈值：
    百分比是钝器 —— 423 条里掉 2 条也才降 0.5%，很容易混过去。
    这里直接看缺口清单：允许剩下的只有空串、纯符号（如 ·）这类
    没有实际内容的文案；只要出现带字母/数字的缺口就退出码 1。

顺带体检插值格式符提示表（tools/key-type-hints.json）：
    stale              —— 表里的文案在上游源码里找不到了（上游改了，表要跟着改）
                          → 视为失败
    unhinted_literals  —— 上游新增了插值文案但还没进表（格式符靠猜，可能猜错）
                          → 只警告，因为缺口检查会兜住猜错的后果

缺口是怎么算出来的、为什么必须是「精确匹配」，见 analyze_coverage.py 的说明。

用法：
    python3 scripts/tools/check-coverage-gap.py [build/coverage.json]
退出码：0 = 通过，1 = 有真缺口或提示表已失效
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT = os.path.join(ROOT, "build", "coverage.json")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(path):
        print("❌ 找不到 %s（先跑 analyze_coverage.py --json）" % path,
              file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)

    miss = d.get("missing_keys", [])
    real = [k for k in miss if re.search(r"\w", k)]
    hints = d.get("hints", {})
    stale = hints.get("stale", [])
    unhinted = hints.get("unhinted_literals", [])

    t = d.get("translatable", {})
    print("A 类文案 %d 条，已覆盖 %d 条，覆盖率 %s%%（精确匹配）"
          % (t.get("distinct_strings", 0), t.get("covered", 0),
             t.get("coverage_percent", "?")))
    print("缺口合计 %d 条，其中带实际内容的 %d 条" % (len(miss), len(real)))
    for k in real:
        print("   ❌ %r" % k)
    print("提示表：%d 条" % hints.get("loaded", 0))
    for k in stale:
        print("   ❌ 提示表里的文案在上游找不到了（上游改了？请同步 key-type-hints.json）：%r" % k)
    for k in unhinted:
        print("   ⚠️ 上游新增的插值文案还没进提示表，格式符靠猜：%r" % k)

    if real:
        print()
        print("修法：把上面列出的 key 补进 zh-Hans.lproj/Localizable.strings。")
        print("      如果缺口是插值文案（源码写成 \"... \\(x) ...\"），先把它的")
        print("      真实格式符（%@ / %lld / %lf）登记到 tools/key-type-hints.json，")
        print("      否则补出来的 key 很可能是错的。")
    if stale:
        print()
        print("修法：提示表是按上游文案原文做索引的，上游改了文案就得跟着改。")

    if real or stale:
        print()
        print("❌ 未通过：%d 条真缺口，%d 条提示表失效" % (len(real), len(stale)))
        return 1
    print()
    print("✅ 通过：A 类缺口只剩无实际内容的文案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
