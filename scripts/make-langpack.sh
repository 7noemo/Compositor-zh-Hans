#!/usr/bin/env bash
#
# 打包语言包发布物
#
#   bash scripts/make-langpack.sh <版本号> [输出目录]
#
# 产出（在输出目录里）：
#   Compositor-zh-Hans-langpack-v<版本>.zip
#       ├── zh-Hans.lproj/Localizable.strings   真正要注入的文件夹
#       ├── 说明.txt                            手动安装与还原的说明
#       ├── 一键安装语言包.command               一键安装（薄壳）
#       └── 一键还原官方版.command               一键还原（薄壳）
#
# 压缩包名刻意用**纯 ASCII**：它要当 GitHub Release 的附件名，
# 而 GitHub 会重命名含非 ASCII 字符的附件名（官方文档 REST API →
# releases → assets 的 Notes 一节写明：「GitHub renames asset filenames
# that have special characters, non-alphanumeric characters…」）。
# 实测：?name=中文名 会被静默改写成 default.xxx，两个中文名还会撞成
# 同一个名字报 422 already_exists —— 这就是 CI 发 Release 失败的原因。
# 注意 zip **内部**的文件名不受这个限制，所以下面就照旧用中文。
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
ZIPNAME="Compositor-zh-Hans-langpack-v${VERSION}.zip"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/compositor-pack.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

mkdir -p "$STAGE/zh-Hans.lproj"
cp "$SRC_PACK" "$STAGE/zh-Hans.lproj/Localizable.strings"

# 顺手把两个一键脚本也塞进压缩包：只想下 zip 的用户照样能拿到完整一套。
# Release 附件名只能是 ASCII，但 zip 内部文件名没有这个限制，
# 所以这里保留中文名，用户解压出来的就是「一键安装语言包.command」。
for f in "一键安装语言包.command" "一键还原官方版.command"; do
  if [ -f "$f" ]; then
    cp "$f" "$STAGE/$f"
    chmod +x "$STAGE/$f"
  else
    echo "⚠️ 找不到 ${f}，压缩包里将不含它" >&2
  fi
done

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
这个压缩包里就带着两个脚本，解压后直接双击：

    一键安装语言包.command     安装（会先帮你备份一份官方原版）

也可以只去仓库 Release 页单独下载。注意 GitHub 的 Release 附件名
只接受 ASCII —— 它会「重命名带特殊字符、非 ASCII 字符的附件名」
（官方文档原文如此）—— 所以 Release 页上这两个文件叫：

    install-zh-Hans.command    就是「一键安装语言包.command」
    restore-official.command   就是「一键还原官方版.command」

功能完全一样，双击即可运行。

还原
----
双击「一键还原官方版.command」（Release 页里叫 restore-official.command）。

注意
----
本语言包只往 app 里放一份 Localizable.strings，不修改任何可执行代码。
因此源码里「先赋给 String 变量、再传给视图」的那部分文案翻不了 ——
SwiftUI 对这类值按原样渲染，不查表。详见仓库 README 的「已知限制」。
TXT

mkdir -p "$OUT"
OUT_ABS="$(cd "$OUT" && pwd)"
rm -f "$OUT_ABS/$ZIPNAME"

# ---------------------------------------------------------------- 打包
# 这里刻意不用 /usr/bin/zip（Info-ZIP）。
#
# Info-ZIP 遇到非 ASCII 文件名时，只把原始 UTF-8 字节写进文件头，
# 却**不会**置「UTF-8 文件名」标志位（general purpose bit 11）。
# 结果：macOS / Linux 的解压工具多半会猜 UTF-8，看着正常；
# 而 Windows 资源管理器按 CP437 解码，用户看到的是
#     Φ»┤µÿÄ.txt
# 这种乱码 —— 而它偏偏是「手动安装说明」那个文件，最需要被看到。
#
# Python 的 zipfile 在文件名无法用 ASCII 编码时会自动置上 bit 11，
# 各平台解压工具都能正确还原。顺带的好处是不依赖外部 zip 命令。
python3 - "$STAGE" "$OUT_ABS/$ZIPNAME" <<'PYZIP'
import os
import sys
import zipfile

stage, out = sys.argv[1], sys.argv[2]

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    # 排序后再写：同一份内容每次打出来的字节完全一致，
    # 便于用 diff / 校验和判断「语言包这次到底有没有变」。
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        rel = os.path.relpath(dirpath, stage)
        if rel != ".":
            # 显式补一条目录项，有些老解压工具依赖它来建文件夹
            z.writestr(zipfile.ZipInfo(rel.replace(os.sep, "/") + "/"), b"")
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            arc = name if rel == "." else os.path.join(rel, name)
            z.write(full, arc)
PYZIP

echo "✅ 已生成：${OUT}/${ZIPNAME}"
echo "   语言包 ${CNT} 条"
echo "   内容："
python3 - "$OUT_ABS/$ZIPNAME" <<'PYLIST'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as z:
    for info in z.infolist():
        # 顺便把编码方式打出来：出现 ASCII 是正常的，
        # 但只要有中文名，那一行必须是 UTF-8（见上面的说明）。
        tag = "UTF-8" if info.flag_bits & 0x800 else "ASCII"
        print("     %-44s %7d B  [%s]" % (info.filename, info.file_size, tag))
PYLIST
