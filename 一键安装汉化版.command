#!/bin/bash
#
# 一键安装 Compositor 简体中文版
#
# 用法：在访达里双击本文件。
#       （首次双击若提示「无法打开」，右键 → 打开 → 打开。）
#
# 这个文件是薄壳：真正的逻辑在 scripts/install.sh。
# 如果你只下载了这一个 .command 而没有克隆整个仓库，
# 它会自动把 install.sh 取下来再跑。
set -uo pipefail

REPO="7noemo/Compositor-zh-Hans"
RAW="https://raw.githubusercontent.com/$REPO/main"

cd "$(dirname "$0")" || exit 1

HERE="$(pwd)"
INSTALLER="$HERE/scripts/install.sh"
TMPDIR_LOCAL=""

if [ ! -f "$INSTALLER" ]; then
  echo "==> 本地没有 scripts/install.sh，先取一份回来"
  TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/compositor-zh.XXXXXX")"
  INSTALLER="$TMPDIR_LOCAL/install.sh"
  mkdir -p "$TMPDIR_LOCAL/scripts"
  if ! curl -fsSL -o "$INSTALLER" "$RAW/scripts/install.sh"; then
    echo "❗ 下载 install.sh 失败。请检查网络，或直接克隆仓库后运行 scripts/install.sh。" >&2
    [ -n "$TMPDIR_LOCAL" ] && rm -rf "$TMPDIR_LOCAL"
    echo
    read -n 1 -s -r -p "按任意键关闭…"
    exit 1
  fi
  INSTALLER="$TMPDIR_LOCAL/install.sh"
fi

bash "$INSTALLER" --repo "$REPO" "$@"
status=$?

[ -n "$TMPDIR_LOCAL" ] && rm -rf "$TMPDIR_LOCAL"

echo
if [ $status -ne 0 ]; then
  echo "❗ 安装过程返回了错误码 ${status}。"
fi
read -n 1 -s -r -p "按任意键关闭窗口…"
exit $status
