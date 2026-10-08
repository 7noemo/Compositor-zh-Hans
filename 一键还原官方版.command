#!/bin/bash
#
# Compositor —— 一键还原官方版
#
# 用法：在访达里双击本文件。
#       （若提示「无法打开」，右键 → 打开 → 打开。）
#
# 这个文件只是一层薄壳，真正的逻辑在 scripts/restore.sh。
# 优先用安装时留下的整包备份还原（官方签名会完整回来）；
# 没有备份时会就地拆掉语言包，并把 Info.plist 恢复成官方值。
set -uo pipefail

REPO="7noemo/Compositor-zh-Hans"
RAW="https://raw.githubusercontent.com/${REPO}/main"
CDN="https://cdn.jsdelivr.net/gh/${REPO}@main"

cd "$(dirname "$0")" || exit 1
HERE="$(pwd)"

RESTORER="$HERE/scripts/restore.sh"
TMP=""

if [ ! -f "$RESTORER" ]; then
  echo "==> 本地没有 scripts/restore.sh，先取一份回来"
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/compositor-zh.XXXXXX")"
  mkdir -p "$TMP/scripts"
  RESTORER="$TMP/scripts/restore.sh"
  if ! curl -fsSL -o "$RESTORER" "$RAW/scripts/restore.sh"; then
    echo "   第一个镜像失败，换 CDN 重试…"
    if ! curl -fsSL -o "$RESTORER" "$CDN/scripts/restore.sh"; then
      echo "❗ 取不到 restore.sh。请检查网络，或直接克隆仓库后运行 scripts/restore.sh。" >&2
      rm -rf "$TMP"
      echo
      read -n 1 -s -r -p "按任意键关闭…"
      exit 1
    fi
  fi
fi

bash "$RESTORER" "$@"
status=$?

[ -n "$TMP" ] && rm -rf "$TMP"

echo
if [ "$status" -ne 0 ]; then
  echo "❗ 还原过程返回了错误码 ${status}。"
fi
read -n 1 -s -r -p "按任意键关闭窗口…"
exit "$status"
