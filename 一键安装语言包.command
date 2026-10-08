#!/bin/bash
#
# Compositor 简体中文语言包 —— 一键安装
#
# 用法：在访达里双击本文件。
#       （若提示「无法打开」，右键 → 打开 → 打开。）
#
# 这个文件只是一层薄壳，真正的逻辑在 scripts/install.sh。
# 如果你只下载了这一个 .command 而没有克隆整个仓库，
# 它会自动把 install.sh 取回来再跑。
set -uo pipefail

REPO="7noemo/Compositor-zh-Hans"
RAW="https://raw.githubusercontent.com/${REPO}/main"
CDN="https://cdn.jsdelivr.net/gh/${REPO}@main"

cd "$(dirname "$0")" || exit 1
HERE="$(pwd)"

INSTALLER="$HERE/scripts/install.sh"
TMP=""

if [ ! -f "$INSTALLER" ]; then
  echo "==> 本地没有 scripts/install.sh，先取一份回来"
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/compositor-zh.XXXXXX")"
  mkdir -p "$TMP/scripts"
  INSTALLER="$TMP/scripts/install.sh"
  if ! curl -fsSL -o "$INSTALLER" "$RAW/scripts/install.sh"; then
    echo "   第一个镜像失败，换 CDN 重试…"
    if ! curl -fsSL -o "$INSTALLER" "$CDN/scripts/install.sh"; then
      echo "❗ 取不到 install.sh。请检查网络，或直接克隆仓库后运行 scripts/install.sh。" >&2
      rm -rf "$TMP"
      echo
      read -n 1 -s -r -p "按任意键关闭…"
      exit 1
    fi
  fi
fi

bash "$INSTALLER" --repo "$REPO" "$@"
status=$?

[ -n "$TMP" ] && rm -rf "$TMP"

echo
if [ "$status" -ne 0 ]; then
  echo "❗ 安装过程返回了错误码 ${status}。"
fi
read -n 1 -s -r -p "按任意键关闭窗口…"
exit "$status"
