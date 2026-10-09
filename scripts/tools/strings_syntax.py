#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`.strings` 语法检查 —— 只保留这一份实现。

为什么要单独一个模块
--------------------
Mac 上有 `plutil`（权威），Linux CI 上没有 plutil，只能走纯 Python 那一版。
这段「纯 Python 版」以前在 check-strings.py 和 merge_translations.py 里各抄了一份，
两份一旦改得不一样就会出现「本地绿、CI 红」。真出过一次：

    块注释 `/* … */` 的**续行**不以 `/*` 或 `*` 开头（以中文开头、行尾才写 `*/`），
    旧版只按行首是不是 `/*`/`*` 判断，于是把这类续行当成非法词条。
    本地 plutil 说 OK，推到 CI（Linux，走纯 Python 版）直接失败。

所以：实现只留一份，两边 import；再在 selfcheck 里强制走纯 Python 版跑一遍，
把「两边判得不一样」挡在本地。

用法
----
    from strings_syntax import lint_strings, lint_python_only
    ok, detail = lint_strings(path)            # 有 plutil 就用 plutil
    ok, detail = lint_python_only(path)        # 强制纯 Python 版（复现 CI 的判定）

环境变量 STRINGS_LINT_FORCE_PY=1 会让 lint_strings() 也走纯 Python 版。
"""
import os
import re
import shutil
import subprocess

# 一条合法词条：  "key" = "value";        （允许行尾 // 注释）
ENTRY_LINE = re.compile(
    r'^\s*(?:"(?:[^"\\]|\\.)*"\s*=\s*"(?:[^"\\]|\\.)*"\s*;\s*(?://.*)?)$')


def lint_python_only(path):
    """纯 Python 版语法检查（CI 在 Linux 上走的就是这一版）。返回 (ok, 详情)。

    逐行检查：每一行要么是空行 / 注释，要么是一条完整的 "k" = "v"; 语句。
    注释用**状态机**处理，而不是只看行首 —— 块注释允许跨行，续行可以长成任何样子
    （这正是过去出错的地方）。
    """
    bad = []
    in_block = False
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            s = line.strip()
            if in_block:
                # 块注释内部：只关心这行有没有把它关掉
                if "*/" in s:
                    in_block = False
                continue
            if not s or s.startswith("//"):
                continue
            if s.startswith("/*"):
                if "*/" not in s:       # 单行注释（/* … */）在这一行就结束了
                    in_block = True
                continue
            if s.startswith("*/"):
                continue
            if not ENTRY_LINE.match(line):
                bad.append("第 %d 行不像合法词条：%s" % (lineno, line[:70]))
    if in_block:
        bad.append("块注释 /* 没有闭合")
    if bad:
        return False, "\n".join(bad[:10])
    return True, "纯 Python 校验通过"


def lint_strings(path, force_python=False):
    """优先用 plutil（权威）；没有 plutil 或强制时用纯 Python 版。

    返回 (ok, 详情)。详情在失败时是给人看的多行文本。
    """
    if force_python or os.environ.get("STRINGS_LINT_FORCE_PY") == "1":
        return lint_python_only(path)
    if shutil.which("plutil"):
        r = subprocess.run(["plutil", "-lint", path],
                           capture_output=True, text=True)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    return lint_python_only(path)
