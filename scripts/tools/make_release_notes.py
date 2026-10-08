#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 GitHub Release 的说明文字（Markdown），写到 stdout。

用法：
    python3 scripts/tools/make_release_notes.py --repo OWNER/REPO --version 1.4.6

数据来源：state/upstream.json（同步流水线维护的版本与覆盖率）。
单独抽出来是因为：写在 workflow 的 bash heredoc 里时，
缩进会与 YAML 的块标量、Python 的多行字符串三方打架，极易出错。
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEMPLATE = """Compositor 的**简体中文语言包**，对应上游 **{up_tag}**（{up_version}）。

> 这里发的是语言包，不是完整应用。
> 请先安装官方 Compositor，再用下面的脚本把语言包挂进去。

## 怎么装

**一键安装（推荐）**

下载本页 Assets 里的 `一键安装语言包.command`，双击运行。
它会自动找到已安装的 Compositor、备份一份官方原版，然后把语言包注入进去。

**手动安装**

下载 `{zip_name}`，解压得到 `zh-Hans.lproj`，把它拷进
`/Applications/Compositor.app/Contents/Resources/` 即可。
手动方式还需要自己改 `Info.plist` 并重签名，细节见仓库 README。

## 想退回官方原版？

下载 `一键还原官方版.command` 双击运行。它会用安装时留下的原版备份整包还原，
官方签名和公证票据都会回来。

## 这一版包含了什么

| 项 | 值 |
| --- | --- |
| 语言包词条 | {strings_total} 条 |
| 扫描到的界面文案 | {found} 条 |
| 已覆盖 | {covered} 条（{pct}%） |
| 仍未覆盖 | {todo} 条 |
| 对应上游版本 | {up_tag} |
| 同步时间 | {last_sync} |

## 已知限制（请务必看一眼）

这是**外挂语言包**：不修改 app 的可执行文件，只往里面放一份
`Localizable.strings`，靠 SwiftUI 自己的本地化查表生效。因此：

* **能翻译的**：源码里直接写成 `Text("Add Layer")` 这类字面量的文案，共扫描到 453 个。
* **翻不了的**：源码里先赋给 `String` 变量、再传给视图的文案（如 `Text(title)`）。
  SwiftUI 对这类值按原样渲染、**不查表**，只有改源码重新编译才能翻译。
  全量扫描到 264 处，其中真正是用户可见文案的约一百处，
  集中在部分工具面板的分组标题、鼠标悬停提示等位置。
  这不是语言包漏了，是外挂方案的能力边界。
* 命令面板（⇧⌘P）的**搜索**仍按英文原文匹配：界面显示中文，但要搜某个工具得输入英文。
* 残留约 {todo} 条未翻译，基本是 `8BIM`、`TySh` 这类 PSD 二进制标记、
  纯数字读数与商品名（MacBook、iPhone 等）—— 翻了反而会出错。

## 环境要求

* macOS **26.0** 或更新（上游 `LSMinimumSystemVersion = 26.0`）
* **Apple 芯片**（上游只发布了 arm64 版本）

## 数据

* 待人工确认的词条：`state/pending/untranslated.tsv`
* 术语表（改这里就能影响下一版用词）：`translations/glossary.tsv`
* 人工校对译文：`translations/curated.tsv`

---

本项目与 Wonder Assembly LLC 无任何隶属关系，
详见仓库 [NOTICE](https://github.com/{repo}/blob/main/NOTICE)。
上游为 MIT 许可；本仓库的语言包与脚本同样以 MIT 发布。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("REPO", ""))
    ap.add_argument("--version", default=os.environ.get("VERSION", ""))
    ap.add_argument("--zip-name", default="", help="语言包压缩包文件名")
    ap.add_argument("--state", default=os.path.join(ROOT, "state", "upstream.json"))
    args = ap.parse_args()

    with open(args.state, encoding="utf-8") as fh:
        st = json.load(fh)
    up = st.get("upstream", {})
    loc = st.get("localized", {})

    def g(d, k, default="?"):
        v = d.get(k)
        return default if v is None else v

    version = args.version or g(up, "latest_version")
    print(TEMPLATE.format(
        up_tag=g(up, "latest_tag"),
        up_version=g(up, "latest_version"),
        version=version,
        repo=args.repo,
        zip_name=args.zip_name or f"Compositor-zh-Hans-语言包-v{version}.zip",
        strings_total=g(loc, "strings_total"),
        found=g(loc, "extracted_ui_strings"),
        covered=g(loc, "covered"),
        pct=g(loc, "coverage_percent"),
        todo=g(loc, "todo"),
        last_sync=g(loc, "last_sync"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
