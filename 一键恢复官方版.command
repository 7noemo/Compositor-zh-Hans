#!/bin/bash
#
# 一键恢复 Compositor 官方原版
#
# 用法：在访达里双击本文件。
#       （首次双击若提示「无法打开」，右键 → 打开 → 打开。）
#
# 这个文件是薄壳：真正的逻辑在 scripts/restore.sh。
# 如果你只下载了这一个 .command 而没有克隆整个仓库，
# 它会自动把 restore.sh 取下来再跑。
set -uo pipefail

REPO="__REPO__"
RAW="https://raw.githubusercontent.com/$REPO/main"

cd "$(dirname "$0")" || exit 1

HERE="$(pwd)"
RESTORER="$HERE/scripts/restore.sh"
TMPDIR_LOCAL=""

if [ ! -f "$RESTORER" ]; then
  echo "==> 本地没有 scripts/restore.sh，先取一份回来"
  TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/compositor-zh.XXXXXX")"
  if ! curl -fsSL -o "$TMPDIR_LOCAL/restore.sh" "$RAW/scripts/restore.sh"; then
    echo "❗ 下载 restore.sh 失败。请检查网络，或直接克隆仓库后运行 scripts/restore.sh。" >&2
    rm -rf "$TMPDIR_LOCAL"
    echo
    read -n 1 -s -r -p "按任意键关闭…"
    exit 1
  fi
  RESTORER="$TMPDIR_LOCAL/restore.sh"
fi

bash "$RESTORER" "$@"
status=$?

[ -n "$TMPDIR_LOCAL" ] && rm -rf "$TMPDIR_LOCAL"

echo
if [ $status -ne 0 ]; then
  echo "❗ 恢复过程返回了错误码 ${status}。"
fi
read -n 1 -s -r -p "按任意键关闭窗口…"
exit $status
