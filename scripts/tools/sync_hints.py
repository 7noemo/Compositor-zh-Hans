#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动维护 tools/key-type-hints.json —— 提示表不再需要人工同步。

背景
----
提示表是按**上游文案原文**做索引的：

    "Zoom in (⌘+), now \\(percent). At 100% each pixel of the JPEG …" -> ["%@"]

上游只要动一个字（把 JPEG 改成 export），这条索引就对不上了。
以前 check-coverage-gap.py 把「对不上」判成失败，于是：

    上游改一句文案 → 提示表失效 → 门禁失败 → 不提交不发布
                   → state 不推进 → 6h 后再跑一模一样 → **永久红**

这个工具把这一步自动化。它做三件事：

1. **保住还成立的条目**：文案还在源码里 → 原样保留。
2. **迁移**：失效条目按文本相似度找它改成了哪一条
   （要求插值个数一致），把格式符列表搬过去 —— 上游改一句话，
   `percent` 是 String 这个**已经核过的事实**不该丢掉。
3. **剪枝**：找不到下家的条目确实是废的，删掉。

代价是提示表会随上游演进自动变准，不再需要人肉 grep 源码。
迁移/删除的动作都打印出来，日志里一眼能看见。

用法：
    python3 scripts/tools/sync_hints.py build/coverage.json
    python3 scripts/tools/sync_hints.py build/coverage.json --dry-run
退出码：0 = 已处理（含「无需改动」）；1 = 输入有问题
"""
import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyze_coverage import SKEL, split_interpolations  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HINTS_PATH = os.path.join(ROOT, "scripts", "tools", "key-type-hints.json")

# 相似度阈值。定得偏松（0.72）是有意的：迁移错一个类型只是多加几条无用条目
# （而且 check-coverage-gap.py 会按「任一候选命中」判定，不会漏），
# 迁移掉了才是真丢信息 —— 那要重新 grep 源码才能补回来。
RATIO_MIN = 0.72
# 与次优候选的最小差距，避免在两句话长得很像时瞎猜
MARGIN_MIN = 0.03


def load_hints(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    t = data.get("types") or {}
    return data, {k: v for k, v in t.items() if isinstance(v, list) and v}


def text_only(s):
    """把插值位置抹成空格，只留「说人话」的部分，用于文本相似度比较。"""
    skel, _args = split_interpolations(s)
    return " ".join(skel.replace(SKEL, " ").split())


def n_interp(s):
    return len(split_interpolations(s)[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coverage", nargs="?",
                    default=os.path.join(ROOT, "build", "coverage.json"),
                    help="analyze_coverage.py --json 的产物（要含 translatable_keys）")
    ap.add_argument("--hints", default=HINTS_PATH)
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写回")
    ap.add_argument("--version", default="", help="把上游版本戳进 _version")
    ap.add_argument("--ratio", type=float, default=RATIO_MIN)
    args = ap.parse_args()

    if not os.path.exists(args.coverage):
        print("❌ 找不到 %s（先跑 analyze_coverage.py --json）" % args.coverage,
              file=sys.stderr)
        return 1
    with open(args.coverage, encoding="utf-8") as fh:
        cov = json.load(fh)
    literals = cov.get("translatable_keys")
    if not literals:
        print("❌ coverage.json 里没有 translatable_keys —— 你用的 analyze_coverage.py"
              " 太旧了，换个新的重跑。", file=sys.stderr)
        return 1
    current = set(literals)

    data, hints = load_hints(args.hints)
    kept, stale, still_ok = {}, [], 0
    for k, v in hints.items():
        if k in current:
            kept[k] = v
            still_ok += 1
        else:
            stale.append(k)

    # 未登记的插值文案才有资格接收迁移（已有登记的不能被覆盖掉）
    pool = [s for s in literals if n_interp(s) and s not in kept]

    migrated, dropped = [], []
    for old in stale:
        n = n_interp(old)
        to = text_only(old)
        best, best_ratio = None, 0.0
        for cand in pool:
            if n_interp(cand) != n:
                continue
            r = difflib.SequenceMatcher(None, to, text_only(cand)).ratio()
            if r > best_ratio:
                best, best_ratio = cand, r
        second = 0.0
        if best is not None:
            for cand in pool:
                if cand == best or n_interp(cand) != n:
                    continue
                r = difflib.SequenceMatcher(None, to, text_only(cand)).ratio()
                second = max(second, r)
        if best is not None and best_ratio >= args.ratio \
                and best_ratio - second >= MARGIN_MIN:
            kept[best] = hints[old]
            pool.remove(best)
            migrated.append((old, best, best_ratio, hints[old]))
        else:
            dropped.append((old, best_ratio))

    print("提示表            : 原有 %d 条" % len(hints))
    print("  ✅ 仍然成立      : %d 条" % still_ok)
    print("  ⚠️ 对不上源码    : %d 条" % len(stale))
    for old, new, r, ph in migrated:
        print("  🔁 迁移到改后的文案（相似度 %.2f，格式符 %s）：" % (r, ph))
        print("       旧 %r" % old)
        print("       新 %r" % new)
    for old, r in dropped:
        print("  🗑 无下家，删除（最高相似度仅 %.2f）：%r" % (r, old))

    changed = bool(migrated or dropped)
    if args.version:
        data["_version"] = "v" + args.version.lstrip("v")
    data["types"] = {k: kept[k] for k in sorted(kept)}

    if args.dry_run:
        print()
        print("（--dry-run：没有写回 %s）" % os.path.relpath(args.hints, ROOT))
        return 0

    with open(args.hints, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print()
    if changed:
        print("已更新 %s：%d 条（迁移 %d，删除 %d）"
              % (os.path.relpath(args.hints, ROOT), len(kept),
                 len(migrated), len(dropped)))
    else:
        print("%s 无需改动（%d 条）" % (os.path.relpath(args.hints, ROOT), len(kept)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
