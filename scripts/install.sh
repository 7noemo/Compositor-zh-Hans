#!/usr/bin/env bash
#
# Compositor 简体中文语言包 —— 安装器
#
# ============================ 它到底做什么 ============================
#
#   Compositor 是 SwiftUI 应用，界面文案在渲染时通过 Localizable.strings 查表。
#   官方版里没有 zh-Hans.lproj，所以永远显示英文。
#   本脚本把一个简体中文语言包「外挂」进官方 app —— 不改一行可执行代码。
#
#     1. 定位 Compositor.app（默认 /Applications/Compositor.app）
#        没装的话，可以直接从上游最新 Release 下载官方版并安装
#     2. 把整个 app 原样备份到
#          ~/Library/Application Support/Compositor-zh-Hans/backup/
#        （约 11 MB；只备份一次，且只备份「还没汉化」的原版）
#     3. 把语言包放进 Contents/Resources/zh-Hans.lproj/Localizable.strings
#     4. 改 Info.plist 三处：
#          CFBundleDevelopmentRegion = zh-Hans   ← 告诉系统优先挑中文 .lproj
#          CFBundleLocalizations     = [zh-Hans]
#          SUEnableAutomaticChecks   = false     ← 很关键，见下
#        Sparkle 自动更新会把官方英文版拉下来覆盖掉汉化，必须切断；
#        SUFeedURL 也改成本仓库的空 feed，连手动「检查更新」也只会得到
#        「已是最新版本」，不会把中文界面换回去。
#     5. xattr -cr 清掉隔离属性，然后分层 ad-hoc 重签。
#        改过 bundle 内容之后原签名必然失效，不重签会打不开
#        （提示「已损坏」或反复闪退）。
#
# ============================ 它不做什么 ============================
#
#   * 不碰 Contents/MacOS/ 下的可执行文件 —— 图像处理逻辑一行不动
#   * 不上传任何数据；唯一的网络行为是下载语言包（以及可选的官方安装包）
#   * 全程不执行 rm -rf；被替换的内容一律先备份
#
# ============================== 用法 ==============================
#
#   bash scripts/install.sh
#   bash scripts/install.sh --yes                    # 不询问
#   bash scripts/install.sh --app ~/Applications/Compositor.app
#   bash scripts/install.sh --pack ./zh-Hans.lproj/Localizable.strings
#   bash scripts/install.sh --repo OWNER/REPO
#
set -euo pipefail

APP_NAME="Compositor"
BUNDLE_ID="com.wonderassembly.compositor"
UPSTREAM_REPO="robbietilton/Compositor"
REPO="7noemo/Compositor-zh-Hans"

# 哨兵刻意拆成两段写：set-repo.sh 会用 sed 全局替换占位符，
# 若这里写成连着的字面量，替换完这行就变成「拿真实仓库名和自己比」，必然误报。
SENTINEL="__RE""PO__"

SUPPORT_DIR="$HOME/Library/Application Support/Compositor-zh-Hans"
BACKUP_APP="$SUPPORT_DIR/backup/$APP_NAME.app"
BACKUP_INFO="$SUPPORT_DIR/backup-info.txt"

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SELF_DIR/.." && pwd)"

ASSUME_YES=0
APP_PATH=""
PACK_PATH=""
NO_INSTALL=0

say()  { printf '%s\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --app)    [ $# -ge 2 ] || die "--app 后面要跟 app 路径";    APP_PATH="$2";  shift 2 ;;
    --pack)   [ $# -ge 2 ] || die "--pack 后面要跟 .strings 路径"; PACK_PATH="$2"; shift 2 ;;
    --repo)   [ $# -ge 2 ] || die "--repo 后面要跟 OWNER/REPO";  REPO="$2";      shift 2 ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --no-install) NO_INSTALL=1; shift ;;
    -h|--help) sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "未知参数：${1}（用 --help 看用法）" ;;
  esac
done

[ "$(uname -s)" = "Darwin" ] || die "这个脚本只能在 macOS 上运行。"

if [ "$REPO" = "$SENTINEL" ] || [ -z "$REPO" ]; then
  die "这个脚本还没配置仓库地址（仍是占位符）。
 请先在仓库根目录运行： bash scripts/set-repo.sh 你的用户名/你的仓库名
 或者手动指定：         bash scripts/install.sh --repo 你的用户名/你的仓库名"
fi
case "$REPO" in
  */*) ;;
  *) die "仓库地址格式不对：${REPO}（应该是 OWNER/REPO）" ;;
esac

WORK="$(mktemp -d "${TMPDIR:-/tmp}/compositor-zh.XXXXXX")"
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
pl_write() {   # 用法: pl_write <app> <Key> <Type> <Value>
  local app="$1" key="$2" type="$3" val="$4" pl
  pl="$(plist_of "$app")"
  if /usr/libexec/PlistBuddy -c "Print :$key" "$pl" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :$key $val" "$pl" >/dev/null
  else
    /usr/libexec/PlistBuddy -c "Add :$key $type $val" "$pl" >/dev/null
  fi
}
pl_delete() {
  /usr/libexec/PlistBuddy -c "Delete :$2" "$(plist_of "$1")" >/dev/null 2>&1 || true
}

say "==================================================="
say " Compositor 简体中文语言包 — 安装"
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
  # Spotlight 兜底：按 bundle id 找，比按名字找准
  APP_PATH="$(mdfind "kMDItemCFBundleIdentifier == '$BUNDLE_ID'" 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
  if [ "$NO_INSTALL" -eq 1 ]; then
    die "没找到 $APP_NAME.app。请先从官方下载安装：
  https://github.com/$UPSTREAM_REPO/releases/latest"
  fi
  say "没找到 $APP_NAME.app。"
  say "接下来会从上游最新 Release 下载官方版并装到 /Applications："
  say "  https://github.com/$UPSTREAM_REPO/releases/latest"
  say ""
  if [ "$ASSUME_YES" -ne 1 ]; then
    printf '现在下载并安装官方版吗？[y/N] '
    read -r ans || ans=""
    case "$ans" in y|Y|yes|YES) ;; *) say "已取消，未做任何改动。"; exit 0 ;; esac
  fi

  say "==> 查询上游最新 Release"
  JSON="$(curl -fsSL "https://api.github.com/repos/$UPSTREAM_REPO/releases/latest" || true)"
  [ -n "$JSON" ] || die "取不到上游 Release 信息（网络不通？或 GitHub API 被限流）。"
  DMG_URL="$(printf '%s' "$JSON" \
    | grep -o '"browser_download_url": *"[^"]*\.dmg"' \
    | head -n 1 \
    | sed 's/.*"\(https[^"]*\)".*/\1/' || true)"
  [ -n "$DMG_URL" ] || die "上游 Release 里没有 .dmg 资产，请手动安装后再运行本脚本。"

  DMG="$WORK/$(basename "$DMG_URL")"
  say "==> 下载 $(basename "$DMG_URL")"
  curl -fL --progress-bar -o "$DMG" "$DMG_URL" || die "下载失败。"
  say "==> 挂载并安装到 /Applications"
  MOUNT_POINT="$WORK/mnt"
  mkdir -p "$MOUNT_POINT"
  hdiutil attach "$DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet || die "挂载失败：${DMG}"
  [ -d "$MOUNT_POINT/$APP_NAME.app" ] || die "DMG 里没有 $APP_NAME.app"
  ditto "$MOUNT_POINT/$APP_NAME.app" "/Applications/$APP_NAME.app" \
    || die "拷贝到 /Applications 失败（权限不足？）"
  hdiutil detach "$MOUNT_POINT" -quiet || true
  MOUNT_POINT=""
  APP_PATH="/Applications/$APP_NAME.app"
fi

say "==> 目标：${APP_PATH}"
APP_VER="$(pl_read "$APP_PATH" CFBundleShortVersionString)"
say "    版本：${APP_VER:-未知}"

# ---------------------------------------------------------------- 2. 写权限预检
#  macOS 13 起有「App 管理」保护：即使是 app 的所有者，也不能随便改 .app 内部。
#  这里先探一下，别等备份都做完了才在第 3 步失败。
PROBE="$APP_PATH/Contents/.compositor-zh-write-probe"
if touch "$PROBE" 2>/dev/null; then
  rm -f "$PROBE"
else
  die "没有权限修改 ${APP_PATH}。

 macOS 从 13 开始有「App 管理」保护。请任选一种方式：
   ① 打开「系统设置 → 隐私与安全性 → App 管理」，把「终端」的开关打开
      （如果列表里没有「终端」，先运行一次本脚本让它出现），然后重新运行本脚本；
   ② 或用管理员权限运行： sudo bash scripts/install.sh --app \"${APP_PATH}\"

 已中止，未做任何改动。"
fi

# ---------------------------------------------------------------- 3. 现状判断
ALREADY=0
if [ -s "$APP_PATH/Contents/Resources/zh-Hans.lproj/Localizable.strings" ]; then
  ALREADY=1
  CUR_CNT="$(grep -c '^"' "$APP_PATH/Contents/Resources/zh-Hans.lproj/Localizable.strings" || true)"
  say "    现状：已汉化（当前语言包 ${CUR_CNT} 条）→ 将更新为新版"
else
  say "    现状：官方英文版 → 将注入中文语言包"
fi

# ---------------------------------------------------------------- 4. 取语言包
if [ -n "$PACK_PATH" ]; then
  [ -f "$PACK_PATH" ] || die "找不到语言包文件：${PACK_PATH}"
  PACK_SRC="本地文件"
elif [ -s "$ROOT_DIR/zh-Hans.lproj/Localizable.strings" ]; then
  PACK_PATH="$ROOT_DIR/zh-Hans.lproj/Localizable.strings"
  PACK_SRC="本仓库"
else
  PACK_PATH="$WORK/Localizable.strings"
  PACK_SRC="在线下载"
  say "==> 下载语言包"
  URLS="https://raw.githubusercontent.com/$REPO/main/zh-Hans.lproj/Localizable.strings
https://cdn.jsdelivr.net/gh/$REPO@main/zh-Hans.lproj/Localizable.strings"
  OKDL=0
  for u in $URLS; do
    if curl -fsSL --connect-timeout 15 -o "$PACK_PATH" "$u"; then
      say "    ✅ $u"
      OKDL=1
      break
    fi
    say "    ⚠️ 取不到：$u"
  done
  [ "$OKDL" -eq 1 ] || die "语言包下载失败。可以克隆仓库后离线安装：
  git clone https://github.com/$REPO.git && bash Compositor-zh-Hans/scripts/install.sh"
fi

PACK_CNT="$(grep -c '^"' "$PACK_PATH" || true)"
[ "${PACK_CNT:-0}" -gt 100 ] || die "语言包看起来不对（只有 ${PACK_CNT} 条）：${PACK_PATH}"

# ---------------------------------------------------------------- 5. 列清单并确认
say ""
say "即将执行："
STEPS=()
if [ "$ALREADY" -eq 0 ] && [ ! -d "$BACKUP_APP" ]; then
  STEPS+=("备份官方原版到 ~/Library/Application Support/Compositor-zh-Hans/backup/")
fi
STEPS+=("写入语言包 zh-Hans.lproj/Localizable.strings（${PACK_CNT} 条，来源：${PACK_SRC}）")
STEPS+=("改 Info.plist：优先中文 + 关掉 Sparkle 自动更新")
STEPS+=("清隔离属性并重新做 ad-hoc 签名")
i=1
for s in "${STEPS[@]}"; do say "  ${i}) ${s}"; i=$((i+1)); done
say ""
warn "重签后本 app 不再有 Apple 公证，首次打开可能需要「右键 → 打开」。"
warn "如果 Compositor 正在运行，装完请退出后重新打开才会看到中文。"
say ""

if [ "$ASSUME_YES" -ne 1 ]; then
  printf '继续吗？[y/N] '
  read -r ans || ans=""
  case "$ans" in y|Y|yes|YES) ;; *) say "已取消，未做任何改动。"; exit 0 ;; esac
fi

# ---------------------------------------------------------------- 6. 备份
if [ "$ALREADY" -eq 0 ]; then
  if [ -d "$BACKUP_APP" ]; then
    say "==> 已有官方原版备份，跳过"
  else
    say "==> 备份官方原版"
    mkdir -p "$SUPPORT_DIR/backup"
    ditto "$APP_PATH" "$BACKUP_APP" || die "备份失败，已中止。"
    {
      printf '版本=%s\n' "${APP_VER:-未知}"
      printf '时间=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
      printf '来源=%s\n' "$APP_PATH"
    } > "$BACKUP_INFO"
    say "    → ${BACKUP_APP}"
  fi
else
  if [ ! -d "$BACKUP_APP" ]; then
    warn "==> ⚠️ 这个 app 之前已被汉化过，而且没有官方原版备份。"
    warn "    想彻底还原时，还原脚本会改为从上游重新下载官方版。"
  fi
fi

# ---------------------------------------------------------------- 7. 注入语言包
say "==> 写入语言包"
DEST_DIR="$APP_PATH/Contents/Resources/zh-Hans.lproj"
mkdir -p "$DEST_DIR"
cp -f "$PACK_PATH" "$DEST_DIR/Localizable.strings" || die "写入语言包失败。"
say "    → ${DEST_DIR}/Localizable.strings（${PACK_CNT} 条）"

# ---------------------------------------------------------------- 8. 改 Info.plist
say "==> 更新 Info.plist"
pl_write "$APP_PATH" CFBundleDevelopmentRegion string zh-Hans
pl_delete "$APP_PATH" CFBundleLocalizations
/usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations array" "$(plist_of "$APP_PATH")" >/dev/null 2>&1 || true
/usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations:0 string zh-Hans" "$(plist_of "$APP_PATH")" >/dev/null 2>&1 || true
# 切断 Sparkle：否则官方自动更新会把汉化覆盖回英文
pl_write "$APP_PATH" SUEnableAutomaticChecks bool false
pl_write "$APP_PATH" SUFeedURL string "https://raw.githubusercontent.com/$REPO/main/appcast.xml"
say "    CFBundleDevelopmentRegion = zh-Hans"
say "    SUEnableAutomaticChecks   = false（防止被更新回英文）"

# ---------------------------------------------------------------- 9. 重签
say "==> 清除隔离属性"
xattr -cr "$APP_PATH" 2>/dev/null || true

say "==> 重新签名（ad-hoc）"
# 从 app 自身导出 entitlements —— 这样任意版本都准确，不依赖源码副本。
# Compositor 带 app-sandbox 等 entitlement，重签时必须原样带上，
# 否则沙箱应用的行为会变（打不开文件、读不了照片等）。
codesign -d --entitlements :- "$APP_PATH" > "$WORK/ent.raw" 2>/dev/null || true
sed -n '/<?xml/,$p' "$WORK/ent.raw" > "$WORK/ent.plist" 2>/dev/null || true
if grep -q '<plist' "$WORK/ent.plist" 2>/dev/null; then
  ENT_OPT="--entitlements $WORK/ent.plist"
  say "    ✅ 已导出原 entitlements（沙箱等权限保持原样）"
else
  ENT_OPT=""
  warn "    ⚠️ 没读到 entitlements（该 app 可能本来就没有）"
fi

# 分层签：内层先签，外层后签。Sparkle 内嵌了 XPC 服务和 Updater.app，
# 漏签它们会导致 app 启动时被 library validation 拦下。
FW="$APP_PATH/Contents/Frameworks/Sparkle.framework"
if [ -d "$FW" ]; then
  say "    签 Sparkle 内嵌组件"
  for xpc in "$FW/Versions/Current/XPCServices"/*.xpc; do
    [ -e "$xpc" ] || continue
    codesign --force --sign - --timestamp=none --deep "$xpc" >/dev/null 2>&1 || \
      warn "      签 $(basename "$xpc") 失败（继续）"
  done
  for inner in "$FW/Versions/Current/Autoupdate" "$FW/Versions/Current/Updater.app"; do
    [ -e "$inner" ] || continue
    codesign --force --sign - --timestamp=none --deep "$inner" >/dev/null 2>&1 || \
      warn "      签 $(basename "$inner") 失败（继续）"
  done
  codesign --force --sign - --timestamp=none "$FW" >/dev/null 2>&1 || \
    warn "      签 Sparkle.framework 失败（继续）"
fi

say "    签 ${APP_NAME}.app"
# shellcheck disable=SC2086
codesign --force --sign - --timestamp=none $ENT_OPT "$APP_PATH" >/dev/null 2>&1 \
  || die "重签失败。app 现在处于「已改内容但签名失效」的状态，
 请立即运行 scripts/restore.sh 还原，或从官方重新安装。"

# ---------------------------------------------------------------- 10. 自检
say "==> 自检"
OK=1
DEST_PACK="$APP_PATH/Contents/Resources/zh-Hans.lproj/Localizable.strings"
if [ -s "$DEST_PACK" ]; then
  N="$(grep -c '^"' "$DEST_PACK" || true)"
  say "    ✅ 语言包就位（${N} 条）"
else
  warn "    ⚠️ 语言包不在位"; OK=0
fi
DEVR="$(pl_read "$APP_PATH" CFBundleDevelopmentRegion)"
if [ "$DEVR" = "zh-Hans" ]; then
  say "    ✅ 开发地区 = zh-Hans"
else
  warn "    ⚠️ 开发地区 = ${DEVR}（预期 zh-Hans）"; OK=0
fi
AUTO="$(pl_read "$APP_PATH" SUEnableAutomaticChecks)"
if [ "$AUTO" = "false" ]; then
  say "    ✅ 已关闭 Sparkle 自动更新"
else
  warn "    ⚠️ SUEnableAutomaticChecks = ${AUTO}（预期 false，汉化可能被覆盖）"
fi
# 注意刻意不用 --verify --strict：Compositor 内嵌 Sparkle.framework，
# 而 strict 模式会对框架里的 Versions/Current 符号链接结构吹毛求疵 ——
# 连官方 Developer ID 签名 + 已公证的原版都过不了。用普通 --verify 即可，
# 它验证的正是我们关心的那件事：签名与 bundle 内容是否匹配。
if codesign --verify "$APP_PATH" >/dev/null 2>&1; then
  say "    ✅ 签名可校验"
else
  warn "    ⚠️ 签名校验未通过；若打不开，请先运行还原脚本再重试"
fi

say ""
say "✅ 完成：${APP_PATH}（版本 ${APP_VER:-未知}）"
if [ -d "$BACKUP_APP" ]; then
  say "   官方原版备份：${BACKUP_APP}"
fi
say "   还原官方版：  bash scripts/restore.sh"
say ""
say "💡 如果 Compositor 正开着，请退出（⌘Q）再重新打开，中文才会生效。"
[ "$OK" -eq 1 ] || warn "   上面有告警项，请留意。"
