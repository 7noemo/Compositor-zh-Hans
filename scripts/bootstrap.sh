#!/usr/bin/env bash
#
# 取上游源码并打上本地化补丁，产物放在 _upstream/。
#
#   scripts/bootstrap.sh [<tag>] [--repo OWNER/REPO]
#
# tag 省略时读 state/upstream.json 里记录的版本。
#
# 这一步只做「源码 → 可编译的汉化源码」，不碰 Xcode、不签名。
# 后面用 scripts/build.sh 编译打包。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UPSTREAM_REPO="${UPSTREAM_REPO:-robbietilton/Compositor}"
SRC_DIR="${SRC_DIR:-$ROOT/_upstream}"
STATE="$ROOT/state/upstream.json"

TAG=""
REPO="${GITHUB_REPOSITORY:-}"
FROM_LOCAL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)       [ $# -ge 2 ] || { echo "--repo 后面要跟 OWNER/REPO" >&2; exit 2; }
                  REPO="$2"; shift 2 ;;
    --src)        [ $# -ge 2 ] || { echo "--src 后面要跟目录" >&2; exit 2; }
                  SRC_DIR="$2"; shift 2 ;;
    --from-local) [ $# -ge 2 ] || { echo "--from-local 后面要跟目录" >&2; exit 2; }
                  FROM_LOCAL="$2"; shift 2 ;;
    -*)           echo "未知参数：$1" >&2; exit 2 ;;
    *)            TAG="$1"; shift ;;
  esac
done
if [ -z "$TAG" ]; then
  # || true：state 文件缺失/损坏时 python 会退出非 0，pipefail + set -e
  # 会让脚本在「读 tag」这一步就无声死掉，而不是给出下面那句可读的报错。
  TAG="$(python3 -c "import json,sys;print(json.load(open('$STATE'))['upstream']['latest_tag'])" 2>/dev/null || true)"
  [ -n "$TAG" ] || { echo "❗ 读不到上游最新 tag，请显式传入，例如： scripts/bootstrap.sh v1.4.6" >&2; exit 2; }
  echo "==> 未指定 tag，沿用 state/upstream.json 里的 $TAG"
fi

if [ -z "$REPO" ]; then
  REPO="$(python3 - <<'PY' 2>/dev/null || true
import json, os
p = "state/upstream.json"
print(json.load(open(p)).get("localized", {}).get("repo", "") if os.path.exists(p) else "")
PY
)"
fi

# 关键：state/upstream.json 里没跑过 set-repo.sh 时存的就是字面量 "__REPO__"。
# 它是「非空字符串」，所以上面那个 [ -z ] 拦不住它 —— 必须显式当空处理，
# 否则会把 Sparkle 更新源、检查更新菜单都写成 https://github.com/__REPO__/... 。
if [ "$REPO" = "__REPO__" ]; then
  REPO=""
fi

if [ -z "$REPO" ]; then
  echo "❗ 请用 --repo OWNER/REPO 告诉脚本你自己的仓库地址（补丁要用它改写更新源）" >&2
  echo "   或者在仓库根目录先跑一次： bash scripts/set-repo.sh 你的用户名/你的仓库名" >&2
  exit 2
fi

echo "==> 上游 : $UPSTREAM_REPO  tag=$TAG"
echo "==> 本仓 : $REPO"
echo "==> 目标 : $SRC_DIR"

rm -rf "$SRC_DIR"
mkdir -p "$(dirname "$SRC_DIR")"

if [ -n "$FROM_LOCAL" ]; then
  # 离线 / 内网构建：直接从本地的上游源码副本拷贝
  [ -d "$FROM_LOCAL/Compositor" ] || {
    echo "❗ --from-local 指向的目录不是 Compositor 源码：$FROM_LOCAL" >&2; exit 2; }
  echo "==> 从本地源码拷贝：$FROM_LOCAL"
  ditto "$FROM_LOCAL" "$SRC_DIR"
else
  # --depth 1 + 指定 tag：只取这一个版本，体积小、速度快
  # http.version=HTTP/1.1：部分代理/企业网络对 git 的 HTTP/2 支持不好，
  # 会报 "Error in the HTTP2 framing layer"，锁到 1.1 最省事。
  echo "==> 克隆上游源码"
  if ! git -c http.version=HTTP/1.1 clone --quiet --depth 1 --branch "$TAG" \
       "https://github.com/$UPSTREAM_REPO.git" "$SRC_DIR"; then
    echo "   浅克隆失败，改成拉取全量再检出该 tag"
    rm -rf "$SRC_DIR"
    git -c http.version=HTTP/1.1 clone --quiet \
      "https://github.com/$UPSTREAM_REPO.git" "$SRC_DIR" \
      || { echo "❗ 无法克隆 ${UPSTREAM_REPO}（网络或代理问题）。" >&2
           echo "  离线场景可以改用： scripts/bootstrap.sh --from-local <本地源码目录>" >&2
           exit 1; }
    git -C "$SRC_DIR" checkout --quiet "$TAG" \
      || { echo "❗ 上游没有 tag $TAG" >&2; exit 1; }
  fi
fi

echo "==> 打本地化补丁"
python3 "$ROOT/scripts/tools/localize_patch.py" "$SRC_DIR" --repo "$REPO"

echo "==> 把语言包放进去（构建后还会再注入一次到 .app 里，双保险）"
mkdir -p "$SRC_DIR/Compositor/zh-Hans.lproj"
cp "$ROOT/zh-Hans.lproj/Localizable.strings" "$SRC_DIR/Compositor/zh-Hans.lproj/"

echo
echo "✅ 就绪：$SRC_DIR"
echo "   下一步： scripts/build.sh"
