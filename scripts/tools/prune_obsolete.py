#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「上游已经删掉 / 改名的文案」在语言包里留下的孤儿 key 清掉。

为什么需要它
------------
merge_translations.py 只会**加**和**改**，从不删。于是上游每改一次文案，
旧 key 就永久留在语言包里：

    v1.4.9 把 «Background for transparency» 改成 «Background»、
    把 «Break the lines into glowing beads» 整句重写、
    把 JPEGExportSheet 换成 ExportAsSheet（于是 «Export JPEG» 作废）…
    → 语言包里就多出 5 条永远查不到的条目

以前靠手工比对删除（v1.4.7 那 4 条就是手工删的）。这个工具把它自动化。

怎么判断「孤儿」
----------------
不比对文案，而是**比对可达 key 的集合**：

    上一轮快照（state/upstream-a-keys.json）里的文案  →  能算出哪些查表 key
    这一轮扫描到的文案                            →  能算出哪些查表 key
    差集 = 上游已经不会再查的 key = 孤儿

存快照而不是存 key 是有意的：文案原文才是稳定标识（key 会随格式符推断变化）。

安全阀
------
* 只删「上一轮有、这一轮没有」的，**不碰**语言包里那些历史遗留的死条目
  （它们来自已废弃的 PR #223 补丁方案，保留作参考 —— 见 README）。
* 只删**确实在语言包里**的条目。
* 一次删超过 --max-delete 条就**中止并报错**。扫描如果出了岔子（比如源码没下全），
  差集会突然暴涨 —— 宁可红一次让人看一眼，也不能批量误删。
* `translations/` 下的 curated.tsv / glossary.tsv / never-translate.txt 里出现的 key
  一律不删（那是人工资产）。
* 支持 --dry-run。

用法：
    python3 scripts/tools/prune_obsolete.py build/coverage.json \
        --pack zh-Hans.lproj/Localizable.strings \
        --snapshot state/upstream-a-keys.json --tag v1.4.9
退出码：0 = 处理完（含「无孤儿」）；1 = 触发安全阀或输入有问题
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyze_coverage as ac  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENTRY_LINE = re.compile(
    r'^\s*"(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*"(?:[^"\\]|\\.)*"\s*;')


def load_lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def first_col(path):
    """读 TSV/txt 的首列，用来保护人工资产。"""
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            out.add(line.split("\t")[0].strip())
    return out


def reachable(literals):
    """一组文案原文 -> 它们可能查表用的全部 key。"""
    keys = set()
    for lit in literals:
        keys.update(ac.key_variants(lit))
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coverage", nargs="?",
                    default=os.path.join(ROOT, "build", "coverage.json"))
    ap.add_argument("--pack", default=os.path.join(ROOT, "zh-Hans.lproj",
                                                   "Localizable.strings"))
    ap.add_argument("--snapshot", default=os.path.join(ROOT, "state",
                                                       "upstream-a-keys.json"))
    ap.add_argument("--hints", default=ac.HINTS_PATH)
    ap.add_argument("--tag", default="", help="本轮上游 tag，写进快照")
    ap.add_argument("--max-delete", type=int, default=40,
                    help="一次最多删多少条；超出即中止（安全阀）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.coverage):
        print("❌ 找不到 %s（先跑 analyze_coverage.py --json）" % args.coverage,
              file=sys.stderr)
        return 1
    with open(args.coverage, encoding="utf-8") as fh:
        cov = json.load(fh)
    cur = cov.get("translatable_keys")
    if cur is None:
        print("❌ coverage.json 里没有 translatable_keys —— analyze_coverage.py 太旧，"
              "换个新的重跑。", file=sys.stderr)
        return 1

    # key_variants 依赖模块级的 HINTS，先装载再算
    ac.HINTS.clear()
    ac.HINTS.update(ac.load_hints(args.hints))

    prev = []
    if os.path.exists(args.snapshot):
        try:
            with open(args.snapshot, encoding="utf-8") as fh:
                prev = json.load(fh).get("keys") or []
        except (OSError, ValueError) as exc:
            print("⚠️ 快照读不出来（%s），本轮只写新快照、不删任何条目。" % exc)
            prev = []
    else:
        print("（没有上一轮快照，本轮只写快照、不删条目 —— 下一轮才开始修剪）")

    cur_set = set(cur)
    vanished = sorted(set(prev) - cur_set)
    orphans = sorted(reachable(vanished) - reachable(cur_set))

    protected = set()
    for name in ("curated.tsv", "glossary.tsv"):
        protected |= first_col(os.path.join(ROOT, "translations", name))
    protected |= first_col(os.path.join(ROOT, "translations", "never-translate.txt"))

    lines = load_lines(args.pack)
    present = {}
    for idx, line in enumerate(lines):
        m = ENTRY_LINE.match(line)
        if m:
            present.setdefault(m.group("key").replace('\\"', '"'), idx)

    to_drop = [k for k in orphans if k in present and k not in protected]
    skipped = [k for k in orphans if k not in present]
    held = [k for k in orphans if k in present and k in protected]

    print("上一轮快照        : %d 条文案" % len(prev))
    print("这一轮扫描        : %d 条文案" % len(cur_set))
    print("  上游已删/改名    : %d 条文案" % len(vanished))
    print("  其中已成为孤儿 key: %d 条" % len(orphans))
    print("  ⏭ 语言包里本来就没有: %d 条" % len(skipped))
    print("  🔒 人工资产里列着，保留: %d 条" % len(held))
    for k in held:
        print("       %r" % k)
    print("  🗑 待删除          : %d 条" % len(to_drop))
    for k in to_drop:
        print("       %r" % k)

    if len(to_drop) > args.max_delete:
        print()
        print("❗ 一次要删 %d 条，超过安全阀 %d 条 —— 中止，一条都不删。"
              % (len(to_drop), args.max_delete))
        print("   这通常意味着扫描出了问题（源码没下全？SKIP_DIRS 变了？），")
        print("   而不是上游真的一次删掉这么多文案。确认无误再调大 --max-delete。")
        return 1

    # 写快照（即使没删也要写，否则下一轮永远拿不到基线）
    snap = {
        "_comment": "上一轮扫描到的 A 类文案原文（含 \"\\(x)\" 插值写法）。"
                    "prune-obsolete.py 拿它对比出上游删掉/改名、因而在语言包里"
                    "成了孤儿的 key。由 CI 自动维护，不要手工编辑。",
        "tag": args.tag,
        "count": len(cur_set),
        "keys": sorted(cur_set),
    }

    if args.dry_run:
        print()
        print("（--dry-run：既没删条目也没写快照）")
        return 0

    dropped_n = 0
    if to_drop:
        drop = set(to_drop)
        kept_lines = []
        for line in lines:
            m = ENTRY_LINE.match(line)
            if m and m.group("key").replace('\\"', '"') in drop:
                dropped_n += 1
                continue
            kept_lines.append(line)
        with open(args.pack, "w", encoding="utf-8") as fh:
            fh.write("\n".join(kept_lines))

        import strings_syntax
        ok, detail = strings_syntax.lint_strings(args.pack)
        if not ok:
            print("❌ 修剪后语言包语法不过，已中止（文件已被改动，请 git checkout 还原）：")
            print(detail)
            return 1

    os.makedirs(os.path.dirname(args.snapshot), exist_ok=True)
    with open(args.snapshot, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print()
    print("已删除 %d 条孤儿 key；快照写至 %s（%d 条）"
          % (dropped_n, os.path.relpath(args.snapshot, ROOT), len(cur_set)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
