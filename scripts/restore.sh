#!/usr/bin/env bash
#
# Compositor 简体中文语言包 —— 还原官方版
#
# ============================ 它做什么 ============================
#
#   按优先级尝试三种还原方式，能做到哪种就做哪种：
#
#     ① 从整包备份还原（首选）
#        安装语言包时会把官方 app 原样备份到
#          ~/Library/Application Support/Compositor-zh-Hans/backup/
#        还原时直接把它拷回去 —— 连原厂 Developer ID 签名和
#        公证票据都是完好的，等于什么都没发生过。
#
#     ② 无备份时，就地拆除
#        删掉 Contents/Resources/zh-Hans.lproj、
#        把 Info.plist 的本地化相关键恢复成官方值（en / 自动更新开启），
#        再重做一次 ad-hoc 签名。
#        界面会立刻回到英文，但签名是 ad-hoc 的（没有原厂私钥，签不回原样）。
#
#     ③ 加 --reinstall 时，直接从上游重新下载官方版覆盖安装
#        这是最彻底的还原，代价是要重新下载约 10 MB。
#
# ============================== 用法 ==============================
#
#   bash scripts/restore.sh
#   bash scripts/restore.sh --yes
#   bash scripts/restore.sh --reinstall        # 从上游重新下载官方版
#   bash scripts/restore.sh --app ~/Applications/Compositor.app
#
set -euo pipefail

APP_NAME="Compositor"
BUNDLE_ID="com.wonderassembly.compositor"
UPSTREAM_REPO="robbietilton/Compositor"

SUPPORT_DIR="$HOME/Library/Application Support/Compositor-zh-Hans"
BACKUP_APP="$SUPPORT_DIR/backup/$APP_NAME.app"
TRASH_DIR="$HOME/.Trash"

ASSUME_YES=0
APP_PATH=""
REINSTALL=0

say()  { printf '%s\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --app)      [ $# -ge 2 ] || die "--app 后面要跟 app 路径"; APP_PATH="$2"; shift 2 ;;
    --yes|-y)   ASSUME_YES=1; shift ;;
    --reinstall) REINSTALL=1; shift ;;
    -h|--help)  sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "未知参数：${1}（用 --help 看用法）" ;;
  esac
done

[ "$(uname -s)" = "Darwin" ] || die "这个脚本只能在 macOS 上运行。"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/compositor-restore.XXXXXX")"
MOUNT_POINT=""
cleanup() {
  if [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ]; then
    hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

plist_of() { printf '%s' "$1/Contents/Info.plist"; }
pl_read()  { /usr/libexec/PlistBuddy -c "Print :$2" "$(plist_of "$1")" 2>/dev/null || true; }

say "==================================================="
say " Compositor — 还原官方版"
say "==================================================="
say ""

# ---------------------------------------------------------------- 1. 定位 app
if [ -n "$APP_PATH" ]; then
  [ -d "$APP_PATH" ] || die "指定的 app 不存在：${APP_PATH}"
elif [ -d "/Applications/$APP_NAME.app" ]; then
  APP_PATH="/Applications/$APP_NAME.app"
elif [ -d "$HOME/Applications/$APP_NAME.app" ]; then
  APP_PATH="$HOME/Applications/$APP_NAME.app"
else
  APP_PATH="$(mdfind "kMDItemCFBundleIdentifier == '$BUNDLE_ID'" 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
  if [ "$REINSTALL" -eq 1 ]; then
    say "没找到 ${APP_NAME}.app，将直接从上游下载安装官方版。"
    APP_PATH="/Applications/$APP_NAME.app"
  else
    die "没找到 ${APP_NAME}.app。如果你其实是想装官方版，请加 --reinstall：
  bash scripts/restore.sh --reinstall"
  fi
else
  say "==> 目标：${APP_PATH}"
  say "    版本：$(pl_read "$APP_PATH" CFBundleShortVersionString)"
  HAS_PACK=0
  [ -e "$APP_PATH/Contents/Resources/zh-Hans.lproj" ] && HAS_PACK=1
  if [ "$HAS_PACK" -eq 1 ]; then
    say "    现状：已装中文语言包"
  else
    say "    现状：看起来没有语言包（可能已经是官方版）"
  fi
fi

if [ -d "$BACKUP_APP" ]; then
  say "    备份：有（${BACKUP_APP}）"
  say "          版本 $(pl_read "$BACKUP_APP" CFBundleShortVersionString)"
else
  say "    备份：无"
fi
say ""

# ---------------------------------------------------------------- 2. 选策略
if [ "$REINSTALL" -eq 1 ]; then
  MODE="reinstall"
  say "将执行：从上游重新下载官方版并覆盖安装（最彻底的还原）"
elif [ -d "$BACKUP_APP" ]; then
  MODE="backup"
  say "将执行：用备份把官方原版整包还原回去（原厂签名与公证都会回来）"
else
  MODE="strip"
  say "将执行：就地拆除中文语言包，并把 Info.plist 的本地化设置恢复为官方值"
  warn "注意：没有原始备份，所以只能重做 ad-hoc 签名，签不回原厂签名。"
  warn "      想要完全干净的官方版，请改用： bash scripts/restore.sh --reinstall"
fi
say ""

if [ "$ASSUME_YES" -ne 1 ]; then
  printf '继续吗？[y/N] '
  read -r ans || ans=""
  case "$ans" in y|Y|yes|YES) ;; *) say "已取消，未做任何改动。"; exit 0 ;; esac
fi

# ---------------------------------------------------------------- 3. 写权限预检
if [ "$MODE" != "reinstall" ] || [ ! -d "$APP_PATH" ]; then
  PROBE_DIR="$APP_PATH/Contents"
  if [ -d "$PROBE_DIR" ]; then
    if touch "$PROBE_DIR/.compositor-zh-write-probe" 2>/dev/null; then
      rm -f "$PROBE_DIR/.compositor-zh-write-probe"
    else
      die "没有权限修改 ${APP_PATH}。

 macOS 从 13 开始有「App 管理」保护。请任选一种方式：
   ① 打开「系统设置 → 隐私与安全性 → App 管理」，把「终端」的开关打开
   ② 或用管理员权限运行： sudo bash scripts/restore.sh --app \"${APP_PATH}\"

 已中止，未做任何改动。"
    fi
  fi
fi

# ---------------------------------------------------------------- 4. 执行
case "$MODE" in

  # ============ ① 从备份整包还原 ============
  backup)
    say "==> 把当前版本移到废纸篓（以防万一）"
    mkdir -p "$TRASH_DIR"
    STAMP="$(date +%Y%m%d-%H%M%S)"
    TRASH_NAME="$APP_NAME-汉化版-$STAMP.app"
    # 用 mv 而不是 rm：同卷重命名，瞬间完成，随时可以在访达里「放回原处」
    mv "$APP_PATH" "$TRASH_DIR/$TRASH_NAME"
    say "    → 废纸篓/${TRASH_NAME}"

    say "==> 从备份拷回官方原版"
    ditto "$BACKUP_APP" "$APP_PATH" || die "从备份还原失败。原版仍在废纸篓：${TRASH_NAME}"
    ;;

  # ============ ② 就地拆除 ============
  strip)
    say "==> 删除中文语言包"
    rm -rf "$APP_PATH/Contents/Resources/zh-Hans.lproj"
    say "    → 已移除 Contents/Resources/zh-Hans.lproj"

    say "==> 恢复 Info.plist"
    PL="$(plist_of "$APP_PATH")"
    # 官方原值：开发地区 en，没有 CFBundleLocalizations，Sparkle 自动更新开启
    if /usr/libexec/PlistBuddy -c 'Print :CFBundleDevelopmentRegion' "$PL" >/dev/null 2>&1; then
      /usr/libexec/PlistBuddy -c 'Set :CFBundleDevelopmentRegion en' "$PL" >/dev/null
    else
      /usr/libexec/PlistBuddy -c 'Add :CFBundleDevelopmentRegion string en' "$PL" >/dev/null
    fi
    /usr/libexec/PlistBuddy -c 'Delete :CFBundleLocalizations' "$PL" >/dev/null 2>&1 || true
    if /usr/libexec/PlistBuddy -c 'Print :SUEnableAutomaticChecks' "$PL" >/dev/null 2>&1; then
      /usr/libexec/PlistBuddy -c 'Set :SUEnableAutomaticChecks true' "$PL" >/dev/null
    else
      /usr/libexec/PlistBuddy -c 'Add :SUEnableAutomaticChecks bool true' "$PL" >/dev/null
    fi
    if /usr/libexec/PlistBuddy -c 'Print :SUFeedURL' "$PL" >/dev/null 2>&1; then
      /usr/libexec/PlistBuddy -c "Set :SUFeedURL https://raw.githubusercontent.com/$UPSTREAM_REPO/main/appcast.xml" "$PL" >/dev/null
    fi
    say "    CFBundleDevelopmentRegion = en"
    say "    SUEnableAutomaticChecks   = true"
    say "    SUFeedURL                 = 上游 feed"

    say "==> 清除隔离属性"
    xattr -cr "$APP_PATH" 2>/dev/null || true

    say "==> 重新签名（ad-hoc）"
    codesign -d --entitlements :- "$APP_PATH" > "$WORK/ent.raw" 2>/dev/null || true
    sed -n '/<?xml/,$p' "$WORK/ent.raw" > "$WORK/ent.plist" 2>/dev/null || true
    if grep -q '<plist' "$WORK/ent.plist" 2>/dev/null; then
      ENT_OPT="--entitlements $WORK/ent.plist"
    else
      ENT_OPT=""
    fi
    FW="$APP_PATH/Contents/Frameworks/Sparkle.framework"
    if [ -d "$FW" ]; then
      for xpc in "$FW/Versions/Current/XPCServices"/*.xpc; do
        [ -e "$xpc" ] || continue
        codesign --force --sign - --timestamp=none --deep "$xpc" >/dev/null 2>&1 || true
      done
      for inner in "$FW/Versions/Current/Autoupdate" "$FW/Versions/Current/Updater.app"; do
        [ -e "$inner" ] || continue
        codesign --force --sign - --timestamp=none --deep "$inner" >/dev/null 2>&1 || true
      done
      codesign --force --sign - --timestamp=none "$FW" >/dev/null 2>&1 || true
    fi
    # shellcheck disable=SC2086
    codesign --force --sign - --timestamp=none $ENT_OPT "$APP_PATH" >/dev/null 2>&1 \
      || warn "    重签失败；app 可能需要在「隐私与安全性」里放行后再打开。"
    ;;

  # ============ ③ 从上游重装 ============
  reinstall)
    say "==> 查询上游最新 Release"
    JSON="$(curl -fsSL "https://api.github.com/repos/$UPSTREAM_REPO/releases/latest" || true)"
    [ -n "$JSON" ] || die "取不到上游 Release 信息（网络不通？或 GitHub API 被限流）。"
    DMG_URL="$(printf '%s' "$JSON" \
      | grep -o '"browser_download_url": *"[^"]*\.dmg"' \
      | head -n 1 \
      | sed 's/.*"\(https[^"]*\)".*/\1/' || true)"
    [ -n "$DMG_URL" ] || die "上游 Release 里没有 .dmg 资产。请手动到
  https://github.com/$UPSTREAM_REPO/releases 下载安装。"

    DMG="$WORK/$(basename "$DMG_URL")"
    say "==> 下载 $(basename "$DMG_URL")"
    curl -fL --progress-bar -o "$DMG" "$DMG_URL" || die "下载失败。"

    say "==> 挂载"
    MOUNT_POINT="$WORK/mnt"
    mkdir -p "$MOUNT_POINT"
    hdiutil attach "$DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet || die "挂载失败：${DMG}"
    [ -d "$MOUNT_POINT/$APP_NAME.app" ] || die "DMG 里没有 $APP_NAME.app"

    if [ -d "$APP_PATH" ]; then
      say "==> 把当前版本移到废纸篓"
      mkdir -p "$TRASH_DIR"
      STAMP="$(date +%Y%m%d-%H%M%S)"
      TRASH_NAME="$APP_NAME-汉化版-$STAMP.app"
      mv "$APP_PATH" "$TRASH_DIR/$TRASH_NAME"
      say "    → 废纸篓/${TRASH_NAME}"
    fi

    say "==> 安装官方版到 $APP_PATH"
    ditto "$MOUNT_POINT/$APP_NAME.app" "$APP_PATH" || die "拷贝失败。"
    hdiutil detach "$MOUNT_POINT" -quiet || true
    MOUNT_POINT=""
    xattr -cr "$APP_PATH" 2>/dev/null || true
    ;;
esac

# ---------------------------------------------------------------- 5. 自检
say "==> 自检"
OK=1
if [ -e "$APP_PATH/Contents/Resources/zh-Hans.lproj" ]; then
  warn "    ⚠️ 语言包目录仍然存在（还原不完整）"; OK=0
else
  say "    ✅ 已无中文语言包"
fi
DEVR="$(pl_read "$APP_PATH" CFBundleDevelopmentRegion)"
if [ "$DEVR" = "en" ]; then
  say "    ✅ 开发地区 = en"
else
  warn "    ⚠️ 开发地区 = ${DEVR}（预期 en，手动装过其他语言包吗？）"
fi
AUTH="$(codesign -dv "$APP_PATH" 2>&1 | sed -n 's/^Authority=//p' | head -n 1 || true)"
if [ -n "$AUTH" ]; then
  say "    ✅ 签名主体：${AUTH}"
else
  say "    ℹ️ 签名主体：未知（ad-hoc 签名没有 Authority，属正常）"
fi
if codesign --verify --strict "$APP_PATH" >/dev/null 2>&1; then
  say "    ✅ 签名可校验"
else
  warn "    ⚠️ 签名校验未通过；首次打开可能需要「右键 → 打开」"; OK=0
fi

say ""
say "✅ 已还原：${APP_PATH}（版本 $(pl_read "$APP_PATH" CFBundleShortVersionString)）"
say ""
say "💡 如果 Compositor 正开着，请退出（⌘Q）再重新打开，界面即回到英文。"
[ "$OK" -eq 1 ] || warn "   上面有告警项，请留意。"
