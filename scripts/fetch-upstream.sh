#!/usr/bin/env bash
#
# 拉取上游源码 —— 只为「扫描界面文案、做差集」，不编译任何东西
#
# 外挂语言包方案不需要编译，但仍然需要读上游源码才能知道
# 「这一版新增了哪些界面文案、哪些旧文案被删掉了」。
#
# 用 codeload 的 tarball 而不是 git clone：
#   * 快得多（几 MB，一次请求，不拉历史）
#   * 不需要 .git，不占空间
#   * 在受限网络里比 git 协议更容易通
#
# 用法：
#   bash scripts/fetch-upstream.sh                  # tag 从 state/upstream.json 读
#   bash scripts/fetch-upstream.sh v1.4.6
#   bash scripts/fetch-upstream.sh v1.4.6 --dest _upstream
#   bash scripts/fetch-upstream.sh --from-local /path/to/源码副本
#
set -euo pipefail

UPSTREAM_REPO="robbietilton/Compositor"
DEFAULT_DEST="_upstream"

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SELF_DIR/.." && pwd)"
STATE="$ROOT_DIR/state/upstream.json"

DEST=""
TAG=""
FROM_LOCAL=""

say()  { printf '%s\n' "$*"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dest)       [ $# -ge 2 ] || die "--dest 后面要跟目录"; DEST="$2"; shift 2 ;;
    --from-local) [ $# -ge 2 ] || die "--from-local 后面要跟目录"; FROM_LOCAL="$2"; shift 2 ;;
    -h|--help)    sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)           die "未知参数：${1}" ;;
    *)            TAG="$1"; shift ;;
  esac
done

DEST="${DEST:-$ROOT_DIR/$DEFAULT_DEST}"
cd "$ROOT_DIR"

# ---------------------------------------------------------------- 本地副本模式
if [ -n "$FROM_LOCAL" ]; then
  [ -d "$FROM_LOCAL" ] || die "找不到源码副本：${FROM_LOCAL}"
  say "==> 使用本地源码副本：${FROM_LOCAL}"
  rm -rf "$DEST"
  mkdir -p "$(dirname "$DEST")"
  cp -R "$FROM_LOCAL" "$DEST"
  # 兼容两种布局：直接是 Compositor/ 或外面还包一层
  if [ ! -d "$DEST/Compositor" ] && [ -d "$DEST"/*/Compositor ]; then
    inner="$(ls -d "$DEST"/*/Compositor | head -n 1)"
    say "    （检测到嵌套目录，取 ${inner} 所在层作为根）"
    tmp="$(dirname "$inner")"
    mv "$tmp" "$DEST.__tmp"
    rm -rf "$DEST"
    mv "$DEST.__tmp" "$DEST"
  fi
  N="$(find "$DEST" -name '*.swift' | wc -l | tr -d ' ')"
  say "    ✅ 就位：${DEST}（${N} 个 Swift 文件）"
  exit 0
fi

# ---------------------------------------------------------------- 确定 tag
if [ -z "$TAG" ]; then
  TAG="$(grep -o '"latest_tag": *"[^"]*"' "$STATE" 2>/dev/null | sed 's/.*"\([^"]*\)".*/\1/' || true)"
  [ -n "$TAG" ] || die "state/upstream.json 里没有 latest_tag，请显式指定： bash scripts/fetch-upstream.sh v1.4.6"
  say "==> 未指定 tag，沿用 state/upstream.json 里的 ${TAG}"
fi

case "$TAG" in
  v*) VERSION="${TAG#v}" ;;
  *)  VERSION="$TAG" ; TAG="v$TAG" ;;
esac

# ---------------------------------------------------------------- 下载
WORK="$(mktemp -d "${TMPDIR:-/tmp}/compositor-src.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

URL="https://codeload.github.com/$UPSTREAM_REPO/tar.gz/refs/tags/$TAG"
say "==> 下载上游源码 ${TAG}"
say "    ${URL}"
curl -fL --connect-timeout 20 --retry 2 -o "$WORK/src.tar.gz" "$URL" \
  || die "下载失败。可改用本地副本：
  bash scripts/fetch-upstream.sh --from-local /path/to/源码副本"

say "==> 解压"
tar -xzf "$WORK/src.tar.gz" -C "$WORK" || die "解压失败。"
SRC_TOP="$(find "$WORK" -maxdepth 1 -type d -name 'Compositor-*' | head -n 1 || true)"
[ -n "$SRC_TOP" ] || die "压缩包里没找到 Compositor-* 目录。"
[ -d "$SRC_TOP/Compositor" ] || die "源码结构异常：${SRC_TOP} 下没有 Compositor/ 目录。"

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
mv "$SRC_TOP" "$DEST"

N="$(find "$DEST" -name '*.swift' | wc -l | tr -d ' ')"
say "    ✅ 就位：${DEST}"
say "       版本 ${VERSION}，${N} 个 Swift 文件"
say ""
say "接下来可以扫描界面文案："
say "  python3 scripts/tools/extract_strings.py \"${DEST}\""
