#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 build/coverage.json，报告 A 类文案还有多少没翻。

为什么不用百分比阈值：
    百分比是钝器 —— 482 条里掉 2 条也才降 0.4%，很容易混过去。
    这里直接看缺口清单本身。

两种模式
--------
默认（CI 用）：**永远退出码 0**。
    只报告 + 把清单写进 build/gaps.json（**不入库**，只在 CI 日志与构建产物里，
    供排查）。查不到的文案**直接跳过** —— 不写待办文件、不开 Issue、不等人。
    为什么这样：以前有缺口就退出码 1，于是整条流水线停摆 —— 不提交、不发布、
    state/upstream.json 不推进，6 小时后再跑条件完全一样，**永久红**。
    改成「记账等人」之后，尾巴变成了「每轮都有人得去看一眼 Issue」。
    2026-10-10 起用户拍板：**取消人工确认** —— 能翻的自动翻，翻不了的就不翻。

--strict（只有本地人工核对时用）：有「带实际内容的缺口」就退出码 1。
    CI **不用**这个模式。

关于 key-type-hints.json 的失效条目：
    提示表是按上游文案原文做索引的，上游改了文案就对不上。
    **这不会让任何用户看到英文** —— 它只是提示表的维护信号，所以只警告。
    真正会修它的是 tools/sync_hints.py（自动把格式符迁移到改后的文案上，
    再剪掉确实没用的），在 CI 里紧跟 analyze_coverage 之后跑。

缺口是怎么算出来的、为什么必须是「精确匹配」，见 analyze_coverage.py 的说明。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_IN = os.path.join(ROOT, "build", "coverage.json")
DEFAULT_OUT = os.path.join(ROOT, "build", "gaps.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coverage", nargs="?", default=DEFAULT_IN,
                    help="analyze_coverage.py --json 的产物")
    ap.add_argument("--strict", action="store_true",
                    help="有带实际内容的缺口就退出码 1（只有本地人工核对时才加）")
    ap.add_argument("--gaps-out", default=DEFAULT_OUT,
                    help="缺口清单写到哪（不入库，仅供排查 / Release 说明引用条数）")
    args = ap.parse_args()

    if not os.path.exists(args.coverage):
        print("❌ 找不到 %s（先跑 analyze_coverage.py --json）" % args.coverage,
              file=sys.stderr)
        return 1
    with open(args.coverage, encoding="utf-8") as fh:
        d = json.load(fh)

    miss = d.get("missing_keys", [])
    # 「带实际内容」= 含字母或数字。空串、单独的 · 之类本来就不该翻。
    real = [k for k in miss if re.search(r"\w", k)]
    symbols = [k for k in miss if not re.search(r"\w", k)]
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
    for k in symbols:
        print("   ·  跳过（无实际内容）：%r" % k)

    print("提示表：%d 条" % hints.get("loaded", 0))
    for k in stale:
        print("   ⚠️ 提示表里的文案在上游找不到了（上游改了文案）—— 不影响显示，"
              "sync_hints.py 会处理：%r" % k)
    for k in unhinted:
        print("   ⚠️ 插值文案还没进提示表，格式符靠猜：%r" % k)

    # ---- 落盘（不入库，仅供排查）----
    gaps = {
        "coverage_percent": t.get("coverage_percent"),
        "distinct_strings": t.get("distinct_strings"),
        "covered": t.get("covered"),
        "missing_total": len(miss),
        "missing_contentful": len(real),
        "missing_keys": real,
        "stale_hints": stale,
        "unhinted_literals": unhinted,
    }
    if args.gaps_out:
        od = os.path.dirname(args.gaps_out)
        if od:
            os.makedirs(od, exist_ok=True)
        with open(args.gaps_out, "w", encoding="utf-8") as fh:
            json.dump(gaps, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    if real:
        print()
        print("ℹ️ %d 条没有译文，**直接跳过**（不写待办、不开 Issue、不等人 ——"
              % len(real))
        print("   2026-10-10 起本项目取消人工确认，见本文件头部说明）。")
        print("   界面上这几条会显示英文；其余不受影响。")
        print("   想自己补的时候再补：把 key<TAB>译文 加进 "
              "translations/curated.tsv（最高权威）。")
        print("   插值文案（源码写成 \"... \\(x) ...\"）的真实格式符若拿不准，")
        print("   登记到 tools/key-type-hints.json，否则补出来的 key 可能是错的。")

    if args.strict and real:
        print()
        print("❌ 严格模式未通过：%d 条真缺口" % len(real))
        return 1

    print()
    if real:
        print("⚠️ %d 条未译，已跳过（清单见 build/gaps.json，不入库）。发布照常进行。"
              % len(real))
    else:
        print("✅ 通过：A 类缺口只剩无实际内容的文案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
