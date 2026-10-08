#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本轮同步的结果写回 state/upstream.json。

单独抽成文件而不是塞在 workflow 的 run: 里，有两个原因：
  * 便于本地复现与测试（workflow 里的 Python 片段没法单独跑）
  * 避免 YAML 块标量 + heredoc 的缩进坑
"""
import argparse
import datetime
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="state/upstream.json")
    ap.add_argument("--tag", required=True, help="上游 tag，如 v1.4.7")
    ap.add_argument("--version", required=True, help="上游版本号，如 1.4.7")
    ap.add_argument("--published", default="", help="上游 Release 的发布时间")
    ap.add_argument("--repo", default="", help="本仓库 OWNER/REPO")
    ap.add_argument("--stats", default="build/stats.json", help="extract_strings.py 产出的统计")
    ap.add_argument("--coverage", default="build/coverage.json",
                    help="analyze_coverage.py 产出的 A/B 类统计")
    ap.add_argument("--release-tag", default="", help="本仓库发出的 Release tag")
    ap.add_argument("--force", action="store_true", help="本轮是手动强制同步")
    ap.add_argument("--github-output", default="", help="要写入的 $GITHUB_OUTPUT 文件")
    args = ap.parse_args()

    stats = {}
    if os.path.exists(args.stats):
        with open(args.stats, encoding="utf-8") as fh:
            stats = json.load(fh)

    cov = {}
    if os.path.exists(args.coverage):
        with open(args.coverage, encoding="utf-8") as fh:
            cov = json.load(fh)

    with open(args.state, encoding="utf-8") as fh:
        st = json.load(fh)

    today = datetime.date.today().isoformat()
    st.setdefault("upstream", {}).update({
        "latest_tag": args.tag,
        "latest_version": args.version,
    })
    if args.published:
        st["upstream"]["published_at"] = args.published

    loc = st.setdefault("localized", {})
    # 口径一：全量字面量扫描（偏保守，含大量不可翻译的噪音）
    for key, stat_key in (
        ("scan_found", "found"),
        ("scan_covered", "covered"),
        ("scan_todo", "todo"),
        ("scan_coverage_percent", "coverage_percent"),
    ):
        if stats.get(stat_key) is not None:
            loc[key] = stats[stat_key]
    if stats.get("strings_total") is not None:
        loc["strings_total"] = stats["strings_total"]
    # 口径二：只看真正的本地化位置 —— 这才是「外挂语言包能翻多少」的答案
    tr = cov.get("translatable") or {}
    un = cov.get("untranslatable") or {}
    if tr:
        loc["translatable_strings"] = tr.get("distinct_strings")
        loc["translatable_covered"] = tr.get("covered")
        loc["coverage_percent"] = tr.get("coverage_percent")
    if un:
        loc["untranslatable_sites"] = un.get("sites")
        loc["untranslatable_expressions"] = un.get("distinct_expressions")

    loc["last_sync"] = today
    if args.repo:
        loc["repo"] = args.repo
    if args.release_tag:
        loc["last_release"] = args.release_tag
    # 编译发行版时代的字段，留着会误导人
    loc.pop("extracted_ui_strings", None)
    loc.pop("covered", None)
    loc.pop("todo", None)
    loc.pop("patched_render_sites", None)
    loc.pop("interp_rules", None)
    loc.pop("last_build", None)

    note = "手动强制同步" if args.force else "上游发新版，自动同步"
    st.setdefault("history", []).insert(0, {
        "tag": args.tag,
        "version": args.version,
        "synced_at": today,
        "strings_total": loc.get("strings_total"),
        "coverage_percent": loc.get("coverage_percent"),
        "release_tag": args.release_tag or None,
        "note": note,
    })
    st["history"] = st["history"][:30]

    with open(args.state, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    pct = loc.get("coverage_percent", "?")
    total = loc.get("strings_total", "?")
    covered = loc.get("translatable_covered", "?")
    found = loc.get("translatable_strings", "?")
    print(f"state 已更新：{args.tag}（{args.version}）")
    print(f"  语言包 {total} 条")
    print(f"  外挂可翻译文案覆盖率 {pct}%（{covered}/{found}）")
    print(f"  外挂翻不了的位置 {loc.get('untranslatable_sites', '?')} 处")
    print(f"  待处理 {loc.get('scan_todo', '?')} 条 -> state/pending/untranslated.tsv")

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"pct={pct}\n")
            fh.write(f"total={total}\n")
            fh.write(f"covered={covered}\n")
            fh.write(f"found={found}\n")
            fh.write(f"b_sites={loc.get('untranslatable_sites', '?')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
