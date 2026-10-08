#!/usr/bin/env bash
#
# 把 _upstream/ 里打过补丁的源码编译成「完整汉化版」app，并打成 DMG。
#
#   scripts/build.sh [--src DIR] [--out DIR]
#
# 依赖：完整 Xcode（不是 Command Line Tools）。
#
# 流程
#   1. xcodebuild Release，ad-hoc 签名（没有 Developer ID 证书也能编）
#   2. 把 zh-Hans.lproj 注入 .app/Contents/Resources/
#      这一步不能用 Xcode 的资源拷贝来做：语言包必须落在 .app 内的
#      Resources 根目录，而 Bundle.main.localizedString(forKey:) 只认那里。
#   3. 把 .app 的 Info.plist 的 CFBundleDevelopmentRegion 改成 zh-Hans，
#      这样即使用户系统语言不是中文，查表也只会命中中文语言包
#   4. 重新 ad-hoc 签名 + 清掉扩展属性（改过内容后原签名一定失效）
#   5. 自检：确认语言包在包里、签名有效、能查到中文
#   6. 打成 DMG
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SRC_DIR="$ROOT/_upstream"
OUT_DIR="$ROOT/dist"
APP_NAME="Compositor"
VOL_NAME="Compositor 简体中文版"

while [ $# -gt 0 ]; do
  case "$1" in
    --src) [ $# -ge 2 ] || { echo "--src 后面要跟源码目录" >&2; exit 2; }
           SRC_DIR="$2"; shift 2 ;;
    --out) [ $# -ge 2 ] || { echo "--out 后面要跟输出目录" >&2; exit 2; }
           OUT_DIR="$2"; shift 2 ;;
    *)     echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

if ! xcodebuild -version >/dev/null 2>&1; then
  echo "❗ 需要完整 Xcode（当前 xcode-select 指向的不是 Xcode，或没装）" >&2
  echo "   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
  exit 2
fi
if [ ! -d "$SRC_DIR/Compositor.xcodeproj" ]; then
  echo "❗ 找不到 $SRC_DIR/Compositor.xcodeproj，请先跑 scripts/bootstrap.sh" >&2
  exit 2
fi
if [ ! -s "zh-Hans.lproj/Localizable.strings" ]; then
  echo "❗ 语言包缺失：zh-Hans.lproj/Localizable.strings" >&2
  exit 2
fi

WORK="$ROOT/build/_build"
rm -rf "$WORK"
mkdir -p "$WORK" "$OUT_DIR"

# ---------------------------------------------------------------- 版本号
echo "==> 读取版本号"
# xcodebuild 在工程缺失 / 未装完整 Xcode 时会返回非 0；set -euo pipefail 下
# 这里不加 || true 的话，脚本会安静退出，看不出到底是哪一步的问题。
if ! SETTINGS="$(xcodebuild -project "$SRC_DIR/Compositor.xcodeproj" -scheme "$APP_NAME" \
      -configuration Release -showBuildSettings 2>/dev/null)"; then
  echo "❗ xcodebuild -showBuildSettings 失败。" >&2
  echo "   常见原因：没有完整 Xcode（xcode-select -p 指向 CommandLineTools）、" >&2
  echo "   或源码没准备好（先跑 scripts/bootstrap.sh）。" >&2
  exit 1
fi
VERSION="$(printf '%s\n' "$SETTINGS" | awk -F' = ' '/ MARKETING_VERSION = /{print $2; exit}' || true)"
BUILD_NO="$(printf '%s\n' "$SETTINGS" | awk -F' = ' '/ CURRENT_PROJECT_VERSION = /{print $2; exit}' || true)"
VERSION="${VERSION:-0.0.0}"
BUILD_NO="${BUILD_NO:-0}"
echo "    $APP_NAME $VERSION ($BUILD_NO)"

# ---------------------------------------------------------------- 1. 编译
echo "==> 编译（Release, ad-hoc 签名）"
# 没有 Developer ID 证书，所以显式指定 ad-hoc（"-"）。
# 注意 CODE_SIGN_STYLE 必须为 Manual，否则 xcodebuild 会去找自动签名证书而失败。
xcodebuild -quiet \
  -project "$SRC_DIR/Compositor.xcodeproj" \
  -scheme "$APP_NAME" \
  -configuration Release \
  -destination "generic/platform=macOS" \
  -derivedDataPath "$WORK/DerivedData" \
  CODE_SIGN_STYLE=Manual \
  CODE_SIGN_IDENTITY="-" \
  CODE_SIGNING_REQUIRED=YES \
  CODE_SIGNING_ALLOWED=YES \
  DEVELOPMENT_TEAM="" \
  PROVISIONING_PROFILE_SPECIFIER="" \
  build

APP_PATH="$WORK/DerivedData/Build/Products/Release/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
  echo "❗ 编译产物不在预期位置：$APP_PATH" >&2
  find "$WORK/DerivedData/Build/Products" -maxdepth 3 -name '*.app' >&2 || true
  exit 1
fi

# ---------------------------------------------------------------- 2. 注入语言包
echo "==> 注入 zh-Hans.lproj"
RES="$APP_PATH/Contents/Resources"
mkdir -p "$RES/zh-Hans.lproj"
cp "$ROOT/zh-Hans.lproj/Localizable.strings" "$RES/zh-Hans.lproj/Localizable.strings"

# ---------------------------------------------------------------- 3. 开发地区
echo "==> 设置 CFBundleDevelopmentRegion = zh-Hans"
PLIST="$APP_PATH/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleDevelopmentRegion zh-Hans" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleDevelopmentRegion string zh-Hans" "$PLIST"

# 只声明 zh-Hans，让 preferredLocalizations 在任何系统语言下都落到中文包
/usr/libexec/PlistBuddy -c "Delete :CFBundleLocalizations" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations array" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations:0 string zh-Hans" "$PLIST"

# ---------------------------------------------------------------- 4. 重签名
echo "==> 重新 ad-hoc 签名"
xattr -cr "$APP_PATH"
# 先签内嵌的 XPC / 框架，再签外层（--deep 在老版本上不可靠，这里显式分层）
#
# 两个细节都要注意：
#   1. 用进程替换 < <(find ...) 而不是 find ... | while read ——
#      加了 set -o pipefail 之后，find 在目录不存在时退出码为 1，
#      会让整条管道「失败」，set -e 于是在这里无声终止打包。
#   2. 顺便加上 [ -d ] 判断，目录不存在就直接跳过。
if [ -d "$APP_PATH/Contents/Frameworks" ]; then
  while IFS= read -r item; do
    codesign --force --sign - --timestamp=none "$item" >/dev/null 2>&1 || true
  done < <(find "$APP_PATH/Contents/Frameworks" -maxdepth 2 \
             \( -name '*.framework' -o -name '*.dylib' \) 2>/dev/null)
fi
if [ -d "$APP_PATH/Contents/XPCServices" ]; then
  while IFS= read -r item; do
    codesign --force --sign - --timestamp=none "$item" >/dev/null 2>&1 || true
  done < <(find "$APP_PATH/Contents/XPCServices" -maxdepth 1 -name '*.xpc' 2>/dev/null)
fi
ENT="$SRC_DIR/Config/Compositor.entitlements"
if [ -f "$ENT" ]; then
  codesign --force --sign - --timestamp=none --entitlements "$ENT" "$APP_PATH"
else
  codesign --force --sign - --timestamp=none "$APP_PATH"
fi
xattr -cr "$APP_PATH"

# ---------------------------------------------------------------- 5. 自检
echo "==> 自检"
fail=0
if [ ! -s "$RES/zh-Hans.lproj/Localizable.strings" ]; then
  echo "   ❌ 语言包没进包" >&2; fail=1
else
  n=$(grep -c '^"' "$RES/zh-Hans.lproj/Localizable.strings" || true)
  echo "   ✅ 语言包就位（$n 条）"
fi
dev=$(/usr/libexec/PlistBuddy -c "Print :CFBundleDevelopmentRegion" "$PLIST" 2>/dev/null || echo "?")
if [ "$dev" = "zh-Hans" ]; then echo "   ✅ CFBundleDevelopmentRegion = zh-Hans"
else echo "   ❌ CFBundleDevelopmentRegion = $dev" >&2; fail=1; fi

if codesign --verify --strict "$APP_PATH" >/dev/null 2>&1; then
  echo "   ✅ 签名校验通过"
else
  echo "   ❌ 签名校验失败" >&2; fail=1
fi
sig=$(codesign -dv "$APP_PATH" 2>&1 | awk -F'=' '/^Signature/{print $2}' || true)
echo "   签名类型：${sig:-未知}"

# 确认语言包里确实有中文，而不是只拷了个空壳
if grep -q '图层' "$RES/zh-Hans.lproj/Localizable.strings"; then
  echo "   ✅ 语言包含中文词条"
else
  echo "   ❌ 语言包里没找到中文（是否只拷了个空壳？）" >&2; fail=1
fi

[ "$fail" -eq 0 ] || { echo "❗ 自检未通过，已中止打包" >&2; exit 1; }

# ---------------------------------------------------------------- 6. 打 DMG
echo "==> 打包 DMG"
STAGE="$WORK/dmg"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$APP_PATH" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

DMG="$OUT_DIR/${APP_NAME}-${VERSION}-zh-Hans.dmg"
rm -f "$DMG"
hdiutil create -quiet -volname "$VOL_NAME" -srcfolder "$STAGE" \
  -ov -format UDZO -fs HFS+ "$DMG"

echo
echo "✅ 完成"
echo "   App : $APP_PATH"
echo "   DMG : $DMG"
echo "   版本: $VERSION ($BUILD_NO)"
echo
echo "   安装：双击 DMG，把 Compositor 拖进「应用程序」。"
echo "   首次打开若被拦截：右键 → 打开；或运行 scripts/install.sh 自动处理。"
