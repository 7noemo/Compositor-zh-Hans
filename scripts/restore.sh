#!/usr/bin/env bash
#
# 一键恢复 Compositor 官方原版
#
#   scripts/restore.sh [--yes] [--tag v1.4.6]
#
# 它会：
#   1. 把当前的汉化版移到废纸篓（不是删除）
#   2. 从上游 robbietilton/Compositor 的 Release 下载官方 DMG
#   3. 装进 /Applications
#
# 如果你更想「原地还原」成安装汉化版之前的那一份，
# 脚本会优先找废纸篓里最近的 Compositor-备份-*.app，问你要不要用它。
set -euo pipefail

UPSTREAM_REPO="robbietilton/Compositor"
APP_NAME="Compositor"
TARGET="/Applications/$APP_NAME.app"
TRASH_DIR="$HOME/.Trash"
ASSUME_YES=0
TAG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) ASSUME_YES=1; shift ;;
    --tag) [ $# -ge 2 ] || { echo "--tag 后面要跟 tag，例如 v1.4.6" >&2; exit 2; }
           TAG="$2"; shift 2 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "这个脚本只能在 macOS 上运行。"

say "=============================================="
say " Compositor — 恢复官方原版"
say "=============================================="
say ""

# ---------------------------------------------------------------- 找可用备份
BACKUP=""
if [ -d "$TRASH_DIR" ]; then
  BACKUP="$(ls -1dt "$TRASH_DIR"/Compositor-备份-*.app 2>/dev/null | head -n 1 || true)"
fi

STEPS=()
if [ -d "$TARGET" ]; then
  CUR_VER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$TARGET/Contents/Info.plist" 2>/dev/null || echo '未知')"
  STEPS+=("把当前的 ${TARGET}（版本 ${CUR_VER}）移到废纸篓")
fi
if [ -n "$BACKUP" ]; then
  BVER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$BACKUP/Contents/Info.plist" 2>/dev/null || echo '未知')"
  STEPS+=("优先用废纸篓里的备份还原：$(basename "$BACKUP")（版本 ${BVER}）")
else
  if [ -n "$TAG" ]; then
    STEPS+=("从上游 $UPSTREAM_REPO 下载 $TAG 官方 DMG")
  else
    STEPS+=("从上游 $UPSTREAM_REPO 下载最新官方 DMG")
  fi
  STEPS+=("把官方 $APP_NAME.app 装进 /Applications")
fi

say "即将执行以下操作："
i=1
for s in "${STEPS[@]}"; do say "  $i) $s"; i=$((i+1)); done
say ""
if [ -n "$BACKUP" ]; then
  say "说明：废纸篓里有备份，脚本优先用它——那是你装汉化版之前的原厂副本，"
  say "      签名与公证都完好，比重新下载更快也更稳。"
  say "      想强制走重新下载，把废纸篓里那份挪走再跑一次即可。"
fi
say ""

if [ "$ASSUME_YES" -ne 1 ]; then
  printf '继续吗？[y/N] '
  read -r ans || ans=""
  case "$ans" in
    y|Y|yes|YES) ;;
    *) say "已取消，未做任何改动。"; exit 0 ;;
  esac
fi

# ---------------------------------------------------------------- 移走当前版本
if [ -d "$TARGET" ]; then
  say "==> 把当前版本移到废纸篓"
  mkdir -p "$TRASH_DIR"
  STAMP="$(date +%Y%m%d-%H%M%S)"
  mv "$TARGET" "$TRASH_DIR/$APP_NAME-汉化版-$STAMP.app"
  say "    → 废纸篓/$APP_NAME-汉化版-$STAMP.app"
fi

# ---------------------------------------------------------------- 还原或下载
if [ -n "$BACKUP" ]; then
  say "==> 用废纸篓里的备份还原"
  ditto "$BACKUP" "$TARGET"
else
  TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/compositor-restore.XXXXXX")"
  MOUNT_POINT=""
  cleanup() {
    [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ] && hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true
    rm -rf "$TMP_DIR"
  }
  trap cleanup EXIT

  if [ -n "$TAG" ]; then
    URL="https://github.com/$UPSTREAM_REPO/releases/download/$TAG/$APP_NAME.dmg"
    say "==> 下载官方 $TAG"
  else
    say "==> 查询官方最新 Release"
    # 赋值里必须 || true：curl 断网时返回非 0，pipefail 会让整条赋值失败，
    # set -e 直接把脚本带走 —— 下面那句 die 的友好提示永远轮不到执行。
    URL="$(curl -fsSL "https://api.github.com/repos/$UPSTREAM_REPO/releases/latest" \
      | sed -n 's/.*"browser_download_url":[[:space:]]*"\([^"]*\.dmg\)".*/\1/p' | head -n 1 || true)"
    [ -n "$URL" ] || die "没找到官方 DMG（网络不通或 Release 里没有 .dmg）。请手动到 https://github.com/$UPSTREAM_REPO/releases 下载。"
    say "    $URL"
  fi

  DMG="$TMP_DIR/$(basename "$URL")"
  curl -fL --progress-bar -o "$DMG" "$URL" || die "下载失败。"

  say "==> 挂载并安装"
  MOUNT_POINT="$TMP_DIR/mnt"
  mkdir -p "$MOUNT_POINT"
  hdiutil attach "$DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet || die "挂载失败。"
  [ -d "$MOUNT_POINT/$APP_NAME.app" ] || die "DMG 里没有 $APP_NAME.app"
  ditto "$MOUNT_POINT/$APP_NAME.app" "$TARGET"
  hdiutil detach "$MOUNT_POINT" -quiet || true
  MOUNT_POINT=""
fi

xattr -cr "$TARGET" 2>/dev/null || true

# ---------------------------------------------------------------- 自检
say "==> 自检"
NEW_VER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$TARGET/Contents/Info.plist" 2>/dev/null || echo '?')"
DEVR="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleDevelopmentRegion' "$TARGET/Contents/Info.plist" 2>/dev/null || echo '?')"
# 同 install.sh：codesign -dv 对未签名包返回非 0，pipefail + set -e 会在这里终止脚本。
# 这两行只是展示用，取不到就显示「未知」，不该把整个脚本带走。
SIG="$(codesign -dv "$TARGET" 2>&1 | awk -F'=' '/^Signature/{print $2}' || true)"
AUTH="$(codesign -dv "$TARGET" 2>&1 | sed -n 's/^Authority=//p' | head -n 1 || true)"
say "    版本     : $NEW_VER"
say "    开发地区 : $DEVR"
say "    签名     : ${SIG:-未知}"
[ -n "$AUTH" ] && say "    签发者   : $AUTH"
if [ -d "$TARGET/Contents/Resources/zh-Hans.lproj" ]; then
  warn "    ⚠️ 包里仍有 zh-Hans.lproj —— 这不应该出现在官方原版上，请检查。"
else
  say "    ✅ 无中文语言包（官方原版特征）"
fi

say ""
say "✅ 已恢复官方原版：${TARGET}（版本 ${NEW_VER}）"
say "   想再装回汉化版：bash scripts/install.sh"
