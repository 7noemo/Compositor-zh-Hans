#!/usr/bin/env bash
#
# 打包语言包发布物
#
#   bash scripts/make-langpack.sh <版本号> [输出目录]
#
# 产出（在输出目录里）：
#   Compositor-zh-Hans-语言包-v<版本>.zip
#       └── zh-Hans.lproj/Localizable.strings   真正要注入的文件夹
#       └── 说明.txt                            手动安装与还原的说明
#
# 单独抽成脚本而不是写在 workflow 的 run: 里：
#   YAML 的块标量 + heredoc 的缩进很容易咬人，而且本地没法单独验证。
#
set -euo pipefail

VERSION="${1:-}"
OUT="${2:-dist}"

if [ -z "$VERSION" ]; then
  echo "用法： bash scripts/make-langpack.sh <版本号> [输出目录]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SRC_PACK="zh-Hans.lproj/Localizable.strings"
[ -s "$SRC_PACK" ] || { echo "❗ 找不到语言包：${SRC_PACK}" >&2; exit 1; }

CNT="$(grep -c '^"' "$SRC_PACK" || true)"
ZIPNAME="Compositor-zh-Hans-语言包-v${VERSION}.zip"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/compositor-pack.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

mkdir -p "$STAGE/zh-Hans.lproj"
cp "$SRC_PACK" "$STAGE/zh-Hans.lproj/Localizable.strings"

cat > "$STAGE/说明.txt" <<'TXT'
Compositor 简体中文语言包
=========================

这是一个「外挂语言包」，不是完整应用。请先安装官方 Compositor。

手动安装
--------
1. 打开终端，执行下面两条（需要管理员权限时前面加 sudo）：

     mkdir -p "/Applications/Compositor.app/Contents/Resources/zh-Hans.lproj"
     cp zh-Hans.lproj/Localizable.strings \
        "/Applications/Compositor.app/Contents/Resources/zh-Hans.lproj/"

2. 改 Info.plist：

     /usr/libexec/PlistBuddy -c "Set :CFBundleDevelopmentRegion zh-Hans" \
       "/Applications/Compositor.app/Contents/Info.plist"
     /usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations array" \
       "/Applications/Compositor.app/Contents/Info.plist"
     /usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations:0 string zh-Hans" \
       "/Applications/Compositor.app/Contents/Info.plist"

   （如果第一条 Set 报错，说明没有这个键，改用 Add / string 形式。）

3. 重签名（改了 app 内容，不重签会打不开）：

     codesign --force --sign - --deep "/Applications/Compositor.app"

4. 退出并重新打开 Compositor，界面即为中文。

更省事的做法
------------
直接下载仓库 Release 里的「一键安装语言包.command」，双击运行，
上面这些步骤它都会做，并且会先帮你备份一份官方原版。

还原
----
同样在 Release 里下载「一键还原官方版.command」双击运行。

注意
----
本语言包只往 app 里放一份 Localizable.strings，不修改任何可执行代码。
因此源码里「先赋给 String 变量、再传给视图」的那部分文案翻不了 ——
SwiftUI 对这类值按原样渲染，不查表。详见仓库 README 的「已知限制」。
TXT

mkdir -p "$OUT"
OUT_ABS="$(cd "$OUT" && pwd)"
rm -f "$OUT_ABS/$ZIPNAME"

( cd "$STAGE" && zip -qr "$OUT_ABS/$ZIPNAME" . )

echo "✅ 已生成：${OUT}/${ZIPNAME}"
echo "   语言包 ${CNT} 条"
echo "   内容："
( cd "$STAGE" && find . -type f | sed 's|^\./|     |' )
