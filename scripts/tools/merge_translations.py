#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把译文表（TSV）合并进 zh-Hans.lproj/Localizable.strings。

* 已存在的 key：就地改写该行译文，保留文件原有的分区注释与顺序
* 新 key：追加到「后续补充」分区
* 重复 key：直接报错，绝不静默生成重复项（.strings 里重复 key 行为未定义）

用法：
    python3 merge_translations.py translations/curated.tsv [translations/auto.tsv ...]

译文表格式（TSV，制表符分隔，首列 key，次列译文；# 与空行忽略）：
    Add layer effect\t添加图层效果
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(ROOT, "zh-Hans.lproj", "Localizable.strings")

ENTRY = re.compile(r'^(?P<indent>\s*)"(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*"'
                   r'(?P<val>(?:[^"\\]|\\.)*)"\s*;\s*(?P<tail>//.*)?$', re.M)
SECTION_MARK = "/* ===== 后续补充"


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def load_tsv(path, strict=True):
    rows, dupes = {}, []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                if strict:
                    print(f"⚠️  {path}:{lineno} 缺少制表符，已跳过：{line[:60]}")
                continue
            key, val = line.split("\t", 1)
            key, val = key.strip(), val
            if not key:
                continue
            if key in rows and rows[key] != val:
                dupes.append((key, rows[key], val))
            rows[key] = val
    return rows, dupes


def lint(path):
    """语法检查。macOS 上用 plutil；其它平台用纯 Python 兜底。

    返回 (ok, 详情)。纯 Python 那一版检查：
      * 每一行要么是空行 / 注释，要么是一条完整的 "k" = "v"; 语句
      * 引号成对，转义合法
    """
    if shutil.which("plutil"):
        r = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True)
        return r.returncode == 0, (r.stdout + r.stderr).strip()

    bad = []
    for lineno, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith(("/*", "*", "//")):
            continue
        if line.strip() == "*/":
            continue
        if not LINE_OK.match(line):
            bad.append(f"第 {lineno} 行不像合法词条：{line[:70]}")
    if bad:
        return False, "\n".join(bad[:10])
    return True, "纯 Python 校验通过"


LINE_OK = re.compile(
    r'^\s*(?:"(?:[^"\\]|\\.)*"\s*=\s*"(?:[^"\\]|\\.)*"\s*;\s*(?://.*)?)$')


def main():
    tsvs = sys.argv[1:]
    if not tsvs:
        print(__doc__)
        return 2

    text = open(PACK, encoding="utf-8").read()
    existing = {}
    for m in ENTRY.finditer(text):
        existing[m.group("key").replace('\\"', '"')] = True

    merged, all_dupes = {}, []
    for t in tsvs:
        p = t if os.path.isabs(t) else os.path.join(ROOT, t)
        rows, dupes = load_tsv(p)
        for k, v in rows.items():
            if k in merged and merged[k] != v:
                all_dupes.append((k, merged[k], v))
            merged[k] = v
        all_dupes += dupes

    if all_dupes:
        print("❌ 译文表内部存在冲突（同一个 key 两个译文）：", file=sys.stderr)
        for k, a, b in all_dupes[:20]:
            print(f"   {k}\n      {a}\n      {b}", file=sys.stderr)
        return 1

    updated, added, same = 0, [], 0
    for key, val in merged.items():
        if key in existing:
            # 就地替换该行译文
            pat = re.compile(
                r'^(\s*)"' + re.escape(esc(key)) + r'"\s*=\s*"(?:[^"\\]|\\.)*"(\s*;.*)$',
                re.M)
            new_text, n = pat.subn(lambda m: f'{m.group(1)}"{esc(key)}" = "{esc(val)}"{m.group(2)}',
                                   text, count=1)
            if n:
                if new_text != text:
                    updated += 1
                else:
                    same += 1
                text = new_text
            else:
                added.append((key, val))
        else:
            added.append((key, val))

    if added:
        if SECTION_MARK not in text:
            text = text.rstrip("\n") + "\n\n" + SECTION_MARK + " ===== */\n\n"
        block = "".join(f'"{esc(k)}" = "{esc(v)}";\n' for k, v in sorted(added))
        text = text.rstrip("\n") + "\n" + block

    # 重复 key 会让 .strings 行为未定义，必须拦住
    seen, dupes = set(), []
    for m in ENTRY.finditer(text):
        k = m.group("key")
        if k in seen:
            dupes.append(k)
        seen.add(k)
    if dupes:
        print(f"❌ 语言包出现重复 key（{len(dupes)} 个）：", file=sys.stderr)
        for k in dupes[:20]:
            print(f"   {k}", file=sys.stderr)
        return 1

    with open(PACK, "w", encoding="utf-8") as fh:
        fh.write(text)

    ok, detail = lint(PACK)
    print(f"就地更新 : {updated}")
    print(f"译文未变 : {same}")
    print(f"新增词条 : {len(added)}")
    print(f"语法校验 : {'✅ 通过' if ok else '❌ 失败'}")
    if not ok:
        print(detail)
        return 1

    total = len({m.group(1) for m in
                 re.finditer(r'^\s*"((?:[^"\\]|\\.)*)"\s*=', text, re.M)})
    print(f"总词条数 : {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
