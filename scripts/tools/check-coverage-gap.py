#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 build/coverage.json，报告 A 类文案还有多少没翻，并把缺口记成账。

为什么不用百分比阈值：
    百分比是钝器 —— 482 条里掉 2 条也才降 0.4%，很容易混过去。
    这里直接看缺口清单本身。

两种模式（2026-10-10 改）
------------------------
默认（宽松，CI 用）：
    只报告，**永远退出码 0**。缺口写进 build/gaps.json，交给后面的步骤
    「记账」—— 进 state/pending/、进 Release 说明、进 Issue。
    为什么改：以前有缺口就退出码 1，于是整条流水线停摆 —— 不提交、不发布、
    state/upstream.json 不推进，6 小时后再跑条件完全一样，**永久红**。
    结果是「一条新文案就能让整个同步停摆」，反而需要人一直守着。

--strict（本地人工核对用）：
    有「带实际内容的缺口」就退出码 1。CI **不再**用这个模式。

关于 key-type-hints.json 的失效条目：
    提示表是按上游文案原文做索引的，上游改了文案就对不上。
    **这不会让任何用户看到英文** —— 它只是提示表的维护信号，
    所以两种模式下都只警告，不再算失败。
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
                    help="有带实际内容的缺口就退出码 1（本地人工核对用，CI 不用）")
    ap.add_argument("--gaps-out", default=DEFAULT_OUT,
                    help="缺口清单写到哪（供 Release 说明 / Issue 记账）")
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

    # ---- 记账 ----
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
        print("修法（任选）：")
        print("  1) 配了 LLM_API_KEY 时，这些通常已被 translate_missing.py 自动翻掉了；")
        print("     还剩下说明 LLM 没处理掉，看看它的日志。")
        print("  2) 手动补：把 key<TAB>译文 加进 translations/curated.tsv。")
        print("  3) 确认不用翻：把 key 加进 translations/never-translate.txt。")
        print("  4) 插值文案（源码写成 \"... \\(x) ...\"）：真实格式符登记到")
        print("     tools/key-type-hints.json，否则补出来的 key 可能是错的。")
        print()
        print("⚠️ 这 %d 条会被记进 state/pending/untranslated.tsv 并照常发布 ——"
              % len(real))
        print("   发布不会因此中止（2026-10-10 起改为此行为，见本文件头部说明）。")

    if args.strict and real:
        print()
        print("❌ 严格模式未通过：%d 条真缺口" % len(real))
        return 1

    print()
    if real:
        print("⚠️ 宽松模式：%d 条缺口已记账（build/gaps.json），继续发布。" % len(real))
    else:
        print("✅ 通过：A 类缺口只剩无实际内容的文案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
