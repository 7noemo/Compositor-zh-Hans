#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shell 脚本雷区检查（本地 + CI 都跑）

检查两类真实踩过的坑：

A. $VAR 后面紧跟多字节字符（中文、全角标点）
   macOS 自带的是 bash 3.2，在 UTF-8 locale 下会把多字节字符当成变量名的一部分：
       say "安装完成：$TARGET（版本 $NEW_VER）"
   会被解析成变量 `TARGET（`，直接报 "unbound variable" 并终止脚本；
   而 LC_ALL=C 或写成 ${TARGET} 就正常。这类错误只在 macOS 的 bash 3.2 上出现，
   Linux 的 bash 5 完全正常 —— 所以在 CI 上看不出来，只在用户机器上炸。
   修法：写成 ${TARGET}（版本 ${NEW_VER}）。

B. 赋值语句里的命令替换可能失败
   set -euo pipefail 下，VAR="$(can_fail | other)" 的退出码就是整个赋值语句的退出码，
   set -e 会因此终止脚本。典型受害者：
       SIG="$(codesign -dv "$APP" 2>&1 | awk ...)"   # 未签名包 → codesign 返回非 0
       URL="$(curl -fsSL "$API" | sed ...)"          # 断网 → curl 返回非 0
       n="$(grep -o 'x' file | wc -l)"               # 无匹配 → grep 返回 1
   后果是脚本「静默死掉」，日志里只剩一句与被影响功能无关的报错。
   修法：末尾补 || true，或把值包进 if，让后面的判空/友好报错有机会执行。

用法：
    python3 scripts/tools/lint-shell.py [仓库根目录]

退出码：0 = 通过（B 类只告警），1 = 有 A 类错误
"""

import re
import sys
from pathlib import Path

# 变量名（含 $1 $@ 这类特殊参数）后面紧跟 0x80 以上的字节
MULTIBYTE_AFTER_VAR = re.compile(
    rb"\$[A-Za-z_][A-Za-z0-9_]*[\x80-\xff]|\$[0-9@*#?!][\x80-\xff]"
)

HAS_SET_E = re.compile(r"^\s*set\s+-[a-z]*e", re.M)

# 形如  VAR="$( ... | ... )"  的单行赋值
PIPE_ASSIGN = re.compile(
    r"""^\s*([A-Za-z_][A-Za-z0-9_]*)="\$\(   # VAR="$(
        (?=[^)]*\|)                          # 内容里必须有管道
        [^)]*\)"\s*$                         # 到 )" 结束
    """,
    re.X | re.M,
)
SAFE_TAIL = re.compile(r"\|\|\s*(true|echo)")

TARGET_SUFFIXES = {".sh", ".bash", ".command", ".zsh"}


def shell_sources(root: Path):
    """收集所有含 shell 代码的文件，返回 [(相对路径, 文本), ...]"""
    out = []

    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts or "build" in p.parts:
            continue
        if p.suffix in TARGET_SUFFIXES or p.name.endswith(".command"):
            try:
                out.append((p, p.read_text(encoding="utf-8")))
            except UnicodeDecodeError:
                pass

    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        try:
            import yaml
        except ImportError:
            print("  （没装 pyyaml，跳过工作流 run: 块的检查）")
            return out
        for p in sorted(wf_dir.glob("*.yml")):
            try:
                doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            for job in (doc or {}).get("jobs", {}).values():
                for st in job.get("steps", []) or []:
                    if st.get("run"):
                        out.append((p, st["run"]))
    return out


def strip_trailing_multibyte(raw: bytes) -> bytes:
    """去掉尾部所有 0x80 以上的字节，只留 $ 和变量名"""
    while raw and raw[-1] >= 0x80:
        raw = raw[:-1]
    return raw


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors, warnings = [], []

    for path, text in shell_sources(root):
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path

        # ---- A 类：$VAR 紧跟多字节字符 ----
        data = text.encode("utf-8")
        for m in MULTIBYTE_AFTER_VAR.finditer(data):
            lineno = data[: m.start()].count(b"\n") + 1
            # 整行注释跳过：注释不会被执行，而文档里往往正需要写出反例。
            # 只跳「行首（可有缩进）就是 #」的行，行内 # 可能是字符串里的字符，不能跳。
            line_start = data.rfind(b"\n", 0, m.start()) + 1
            line_end = data.find(b"\n", m.start())
            raw_line = data[line_start : line_end if line_end != -1 else len(data)]
            if raw_line.lstrip().startswith(b"#"):
                continue
            name = strip_trailing_multibyte(data[m.start() : m.end()])[1:].decode("ascii")
            frag = data[m.start() : m.start() + 28].decode("utf-8", "replace")
            errors.append(
                f'{rel}:{lineno}: ${name} 后面紧跟多字节字符 → 改成 ${{{name}}}\n'
                f"      {frag!r}"
            )

        # ---- B 类：set -e 下的管道赋值 ----
        if HAS_SET_E.search(text):
            for m in PIPE_ASSIGN.finditer(text):
                line = m.group(0)
                if SAFE_TAIL.search(line):
                    continue
                lineno = text[: m.start()].count("\n") + 1
                warnings.append(f'{rel}:{lineno}: {m.group(1)}="$(' + " ... | ... )\" 缺少 || true")

    for w in warnings:
        print(f"  ⚠️  {w}")
    for e in errors:
        print(f"  ❌ {e}")
    print()
    print(f"  A 类（会在 macOS bash 3.2 上崩溃）：{len(errors)} 处")
    print(f"  B 类（pipefail 下可能静默终止）：{len(warnings)} 处")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
