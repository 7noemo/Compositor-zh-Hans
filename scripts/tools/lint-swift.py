#!/usr/bin/env python3
"""检查补丁生成的 L() 调用「结构上」是否可能成立。

为什么需要这个
--------------
CI 里 selfcheck 的 `swiftc -parse` 只做**语法**分析，下面这些写法全都是
语法合法、要到编译期才报错的：

    Label(L("New", systemImage: "plus"))   -> extra argument in call
                                              （L() 只收一个参数）
    Label(L(verbatim: "New"))              -> 函数调用里不能出现参数标签

而这种错误会让 `xcodebuild` 直接以 65 退出、整条出包流水线死掉，
本地 `swiftc -parse` 却一路绿灯 —— 于是「自检全过、CI 必挂」，
只能靠 15 分钟的 macOS runner 来回试错。

所以这里用纯文本扫描在编译**之前**拦一道。它不是类型检查，只做
「这个 L() 的实参形状对不对」这一件事。

判定规则
--------
L() / LF() 的第一个括号内（配平 + 字符串字面量感知）如果出现：

  * 顶层逗号           -> 多个实参。L() 只收一个，必然编译失败。
  * 顶层参数标签 `x:`  -> 函数调用里带标签，必然编译失败。

LF() 是可变参数（LF("...", a, b)），顶层逗号是正常的，只查标签和配平。
"""

import re
import sys
from pathlib import Path

CALL = re.compile(r"(?<![A-Za-z0-9_.])(L|LF)\(")
LABEL = re.compile(r"^\s*[A-Za-z_]\w*\s*:")


def find_close(text, open_idx):
    """open_idx 指向 '('，返回配对 ')' 的下标；字符串字面量里的括号不计入。

    找不到配对返回 -1（跨行调用会被跳过 —— 上游视图代码基本一行一处，
    加上 swiftc -parse 也会兜住真正的括号错误）。
    """
    depth = 0
    i, n = open_idx, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def top_level_commas(s):
    depth = 0
    i, n, count = 0, len(s), 0
    while i < n:
        c = s[i]
        if c == '"':
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == "," and depth == 0:
            count += 1
        i += 1
    return count


def check(root):
    errors = []
    total = 0
    for path in sorted(Path(root).rglob("*.swift")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        rel = path.relative_to(root)
        for m in CALL.finditer(text):
            close = find_close(text, m.end() - 1)
            if close < 0:
                continue
            name = m.group(1)
            arg = text[m.end():close]
            lineno = text[: m.start()].count("\n") + 1
            src = lines[lineno - 1].strip() if lineno <= len(lines) else ""
            total += 1

            if name == "L" and top_level_commas(arg) > 0:
                errors.append(
                    f"{rel}:{lineno}: L() 收到多个实参（只接受一个 key）\n"
                    f"      {src[:120]}\n"
                    f"      -> 多参数调用要只包第一个实参："
                    f"Label(L(\"文案\"), systemImage: \"icon\")"
                )
            if LABEL.match(arg):
                errors.append(
                    f"{rel}:{lineno}: L()/{name}() 的实参带参数标签\n"
                    f"      {src[:120]}\n"
                    f"      -> 函数调用里不能写标签，应把实参表达式整个包起来"
                )
    return total, errors


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "_upstream/Compositor"
    if not Path(root).is_dir():
        print(f"❌ 目录不存在：{root}", file=sys.stderr)
        return 2

    total, errors = check(root)
    print(f"扫描 {root}：L()/LF() 调用点 {total} 个")
    if errors:
        print(f"\n发现 {len(errors)} 处结构性错误（swiftc -parse 检查不出来，"
              f"但 xcodebuild 一定会失败）：\n")
        for e in errors:
            print(f"  {e}")
        return 1
    print("✅ L()/LF() 调用形状正确（单实参、无参数标签）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
