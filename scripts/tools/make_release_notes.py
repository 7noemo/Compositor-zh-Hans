#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 GitHub Release 的说明文字（Markdown），写到 stdout。

用法：
    python3 scripts/tools/make_release_notes.py --repo OWNER/REPO --version 1.4.6

数据来源：state/upstream.json（同步流水线维护的版本与覆盖率）。
单独抽出来是因为：把它写在 workflow 的 bash heredoc 里，
缩进会与 YAML 的块标量、Python 的多行字符串三方打架，极易出错。
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEMPLATE = """为上游 **{up_tag}**（{up_version}）准备的完整简体中文版。

## 怎么装

**方式一：一键安装（推荐）**

从下面的 Assets 里下载 `一键安装汉化版.command`，双击即可。
它会自动下载 DMG、安装到「应用程序」，并把旧版本移到废纸篓（不是删除，随时可放回）。

**方式二：手动安装**

下载 `Compositor-{version}-zh-Hans.dmg`，双击挂载，把 `Compositor` 拖进「应用程序」。
首次打开若被 Gatekeeper 拦下：右键 → 打开。

## 想退回官方原版？

下载 `一键恢复官方版.command` 双击运行即可。

## 这一版包含了什么

| 项 | 值 |
| --- | --- |
| 语言包词条 | {strings_total} 条 |
| 扫描到的界面文案 | {found} 条 |
| 已覆盖 | {covered} 条（{pct}%） |
| 仍未覆盖 | {todo} 条 |
| 同步时间 | {last_sync} |

构建时对上游源码做了三类改动：

1. **注入运行时查表助手** `L()` / `LF()`（新增 `Compositor/Localized.swift`）；
2. **把「先存成 String 再进视图」的文案包一层 `L()`** —— 这类文案 SwiftUI 按原样渲染、
   不查表，是外挂语言包永远覆盖不到的根因，也是「小工具组件 / 弹窗提示仍是英文」的原因；
3. **把字符串插值消息改写成显式格式串**，让它们能被查表命中。

另外切断了 Sparkle 自动更新链路，避免汉化版被更新回英文原版。

## 已知限制

* 命令面板（⇧⌘P）的**搜索**仍按英文原文匹配：显示是中文，但要搜到某个工具得输入英文。
* 未做 Apple 公证（ad-hoc 签名），首次打开可能需要一次「右键 → 打开」；
  用一键安装脚本装的话会自动清掉隔离属性，省掉这一步。
* 残留约 {todo} 条未翻译，基本是 `8BIM`、`TySh` 这类 PSD 二进制标记、
  纯数字读数与商品名（MacBook、iPhone 等）。
* 截图中若有英文残留，欢迎提 Issue 附截图，会比文字描述好定位。

## 数据

* 待人工确认的词条：`state/pending/untranslated.tsv`
* 术语表（改这里就能影响下一版用词）：`translations/glossary.tsv`
* 人工校对译文：`translations/curated.tsv`

---

本发行版与 Wonder Assembly LLC 无任何隶属关系，详见仓库 [NOTICE](https://github.com/{repo}/blob/main/NOTICE)。
上游为 MIT 许可；本项目对上游的改动同样以 MIT 发布。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("REPO", ""))
    ap.add_argument("--version", default=os.environ.get("VERSION", ""))
    ap.add_argument("--state", default=os.path.join(ROOT, "state", "upstream.json"))
    args = ap.parse_args()

    st = json.load(open(args.state, encoding="utf-8"))
    up = st.get("upstream", {})
    loc = st.get("localized", {})

    def g(d, k, default="?"):
        v = d.get(k)
        return default if v is None else v

    print(TEMPLATE.format(
        up_tag=g(up, "latest_tag"),
        up_version=g(up, "latest_version"),
        version=args.version or g(up, "latest_version"),
        repo=args.repo,
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
