#!/usr/bin/env bash
#
# 一键安装 Compositor 简体中文版
#
#   scripts/install.sh [--from <DMG 路径>] [--yes]
#
# 它会：
#   1. 检查当前是否已装 Compositor；装了就先把原版移到废纸篓（不是删除，可随时找回）
#   2. 从本仓库最新的 GitHub Release 下载 DMG（或使用 --from 指定的本地 DMG）
#   3. 挂载 → 把 Compositor.app 拷进 /Applications → 卸载
#   4. 清掉隔离属性，让 ad-hoc 签名的应用可以直接打开
#
# 安全约定（重要）：
#   * 全程不执行 rm -rf，被替换的旧版本一律进废纸篓
#   * 动手之前会把「要做什么」列清楚，等你确认（除非加 --yes）
#   * 装完把备份位置告诉你，想退回原版就跑 scripts/restore.sh
set -euo pipefail

REPO_DEFAULT="7noemo/Compositor-zh-Hans"
REPO="${REPO_OVERRIDE:-$REPO_DEFAULT}"
APP_NAME="Compositor"
TARGET="/Applications/$APP_NAME.app"
TRASH_DIR="$HOME/.Trash"
ASSUME_YES=0
LOCAL_DMG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --from) [ $# -ge 2 ] || { echo "--from 后面要跟 DMG 路径" >&2; exit 2; }
            LOCAL_DMG="$2"; shift 2 ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --repo) [ $# -ge 2 ] || { echo "--repo 后面要跟 OWNER/REPO" >&2; exit 2; }
            REPO="$2"; shift 2 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 环境检查
[ "$(uname -s)" = "Darwin" ] || die "这个脚本只能在 macOS 上运行。"

# 建仓后没跑过 set-repo.sh 的话，这里会是占位符。提前拦住，别让人对着 404 发懵。
# 注意：哨兵值刻意拆成两段写 —— set-repo.sh 会用 sed 全局替换占位符，
# 若这里写成连着的字面量，替换后这行会变成「拿真实仓库名和自己比」，必然命中。
SENTINEL="__RE""PO__"
if [ "$REPO" = "$SENTINEL" ] || [ -z "$REPO" ]; then
  die "这个脚本还没配置仓库地址（仍是占位符）。
 请先运行： bash scripts/set-repo.sh 你的用户名/你的仓库名
 或者手动指定： bash scripts/install.sh --repo 你的用户名/你的仓库名"
fi
case "$REPO" in
  */*) ;;
  *) die "仓库地址格式不对：${REPO}（应为 OWNER/REPO）" ;;
esac

say "=============================================="
say " Compositor 简体中文版 — 一键安装"
say "=============================================="
say ""

# ---------------------------------------------------------------- 收集变更
STEPS=()
if [ -d "$TARGET" ]; then
  OLD_VER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$TARGET/Contents/Info.plist" 2>/dev/null || echo '未知')"
  # 末尾必须 || true：codesign -dv 对未签名 / 被破坏的包会返回非 0，
  # 在 set -euo pipefail 下这条赋值会直接终止脚本 —— 而且是在打印完 banner 之后，
  # 用户只看到标题就没了。OLD_SIG 只是用来显示，取不到就算了。
  OLD_SIG="$(codesign -dv "$TARGET" 2>&1 | awk -F'=' '/^Signature/{print $2}' || true)"
  STEPS+=("把现有的 ${TARGET}（版本 ${OLD_VER}，签名 ${OLD_SIG:-未知}）移到废纸篓")
fi
if [ -n "$LOCAL_DMG" ]; then
  [ -f "$LOCAL_DMG" ] || die "找不到 DMG：$LOCAL_DMG"
  STEPS+=("从本地 DMG 安装：$LOCAL_DMG")
else
  STEPS+=("从 https://github.com/$REPO/releases/latest 下载最新 DMG")
fi
STEPS+=("把 $APP_NAME.app 拷贝到 /Applications")
STEPS+=("清除隔离属性（xattr -cr），使 ad-hoc 签名的应用可以直接打开")

say "即将执行以下操作："
i=1
for s in "${STEPS[@]}"; do say "  $i) $s"; i=$((i+1)); done
say ""
warn "注意：本汉化版是 ad-hoc 签名、未经 Apple 公证。"
warn "      旧版本会进废纸篓（不是删除），随时可以拖回来。"
say ""

if [ "$ASSUME_YES" -ne 1 ]; then
  printf '继续吗？[y/N] '
  read -r ans || ans=""
  case "$ans" in
    y|Y|yes|YES) ;;
    *) say "已取消，未做任何改动。"; exit 0 ;;
  esac
fi

# ---------------------------------------------------------------- 备份 + 替换
if [ -d "$TARGET" ]; then
  say "==> 把旧版本移到废纸篓"
  mkdir -p "$TRASH_DIR"
  STAMP="$(date +%Y%m%d-%H%M%S)"
  BACKUP_NAME="$APP_NAME-备份-$STAMP.app"
  # mv 到废纸篓：可随时在 Finder 里「放回原处」
  mv "$TARGET" "$TRASH_DIR/$BACKUP_NAME"
  say "    → 废纸篓/$BACKUP_NAME"
  say "    想直接回滚也可以：mv ~/.Trash/$BACKUP_NAME /Applications/"
fi

# ---------------------------------------------------------------- 取 DMG
DMG="$LOCAL_DMG"
MOUNT_POINT=""
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/compositor-install.XXXXXX")"
cleanup() {
  if [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ]; then
    hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if [ -z "$DMG" ]; then
  say "==> 查询最新 Release"
  API="https://api.github.com/repos/$REPO/releases/latest"
  JSON="$(curl -fsSL "$API")" || die "无法访问 ${API}（网络或仓库名有误？）"
  URL="$(printf '%s' "$JSON" \
    | sed -n 's/.*"browser_download_url":[[:space:]]*"\([^"]*\.dmg\)".*/\1/p' \
    | head -n 1)"
  [ -n "$URL" ] || die "最新 Release 里没有 .dmg 资产，请检查仓库的 Releases 页。"
  say "    $URL"
  DMG="$TMP_DIR/$(basename "$URL")"
  say "==> 下载"
  curl -fL --progress-bar -o "$DMG" "$URL" || die "下载失败。"
else
  say "==> 使用本地 DMG"
fi

# ---------------------------------------------------------------- 挂载 + 拷贝
say "==> 挂载 DMG"
MOUNT_POINT="$TMP_DIR/mnt"
mkdir -p "$MOUNT_POINT"
hdiutil attach "$DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet \
  || die "挂载失败：$DMG"

SRC_APP="$MOUNT_POINT/$APP_NAME.app"
[ -d "$SRC_APP" ] || die "DMG 里没有 $APP_NAME.app"

say "==> 安装到 /Applications"
# 用 ditto 而不是 cp -R：它会保留签名所需的资源分支与权限
ditto "$SRC_APP" "$TARGET"

say "==> 卸载 DMG"
hdiutil detach "$MOUNT_POINT" -quiet || true
MOUNT_POINT=""

# ---------------------------------------------------------------- 去隔离
say "==> 清除隔离属性"
xattr -cr "$TARGET" 2>/dev/null || true

# ---------------------------------------------------------------- 自检
say "==> 自检"
OK=1
if [ -s "$TARGET/Contents/Resources/zh-Hans.lproj/Localizable.strings" ]; then
  CNT="$(grep -c '^"' "$TARGET/Contents/Resources/zh-Hans.lproj/Localizable.strings" || true)"
  say "    ✅ 语言包就位（$CNT 条）"
else
  warn "    ⚠️ 没找到语言包：$TARGET/Contents/Resources/zh-Hans.lproj/"
  OK=0
fi
DEVR="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleDevelopmentRegion' "$TARGET/Contents/Info.plist" 2>/dev/null || echo '?')"
if [ "$DEVR" = "zh-Hans" ]; then
  say "    ✅ 开发地区 = zh-Hans"
else
  warn "    ⚠️ 开发地区 = ${DEVR}（预期 zh-Hans）"
fi
if codesign --verify --strict "$TARGET" >/dev/null 2>&1; then
  say "    ✅ 签名可校验"
else
  warn "    ⚠️ 签名校验未通过，首次打开可能需要「右键 → 打开」"
fi
NEW_VER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$TARGET/Contents/Info.plist" 2>/dev/null || echo '?')"

say ""
say "✅ 安装完成：${TARGET}（版本 ${NEW_VER}）"
# 注意顺序：必须先判「变量有没有定义」再判「目录在不在」。
# 全新机器（此前没装过 Compositor）时 BACKUP_NAME 是未定义变量，
# set -u 会在展开 "$TRASH_DIR/$BACKUP_NAME" 的那一刻直接终止脚本 ——
# 而且是在安装已经成功之后，用户会以为整件事失败了。
if [ -n "${BACKUP_NAME:-}" ] && [ -d "$TRASH_DIR/$BACKUP_NAME" ]; then
  say "   旧版本备份：废纸篓/$BACKUP_NAME"
fi
say "   还原官方原版：bash scripts/restore.sh"
[ "$OK" -eq 1 ] || warn "   有告警项，见上。"
