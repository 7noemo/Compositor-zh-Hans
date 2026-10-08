#!/usr/bin/env bash
#
# 把仓库里所有 __REPO__ 占位符替换成你自己的 GitHub 仓库地址。
#
#   scripts/set-repo.sh OWNER/REPO
#
# 建仓之后跑一次就够了（CI 里也会自动跑，见 .github/workflows/*.yml）。
# 需要替换的地方：
#   * scripts/bootstrap.sh / install.sh      —— 补丁改写更新源、装完提示
#   * 一键安装汉化版.command / 一键恢复官方版.command
#   * .github/workflows/*.yml                —— Release 通知文案
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO="${1:-}"
if ! printf '%s' "$REPO" | grep -Eq '^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$'; then
  echo "用法： scripts/set-repo.sh OWNER/REPO" >&2
  echo "例：   scripts/set-repo.sh zhangsan/Compositor-zh-Hans" >&2
  exit 2
fi

FILES=(
  "scripts/bootstrap.sh"
  "scripts/build.sh"
  "scripts/install.sh"
  "scripts/restore.sh"
  "scripts/tools/localize_patch.py"
  "state/upstream.json"
  "一键安装汉化版.command"
  "一键恢复官方版.command"
)

# 刻意不动 README.md：里面出现的 __REPO__ 是「教你怎么替换」的示例文本，
# 替换掉反而看不懂了。

# macOS 自带 BSD sed，用 -i '' ；GNU sed 用 -i
sed_inplace() {
  if sed --version >/dev/null 2>&1; then
    sed -i "s|__REPO__|$REPO|g" "$1"
  else
    sed -i '' "s|__REPO__|$REPO|g" "$1"
  fi
}

total=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  # 两个坑叠在一起：
  #   1) grep -c 无匹配时会打印 0 并且以 1 退出，再 || echo 0 就输出两行，
  #      后面 [ "$n" -gt 0 ] 直接报 "integer expression expected"。
  #      → 改用 grep -o | wc -l，输出永远是一行数字。
  #   2) set -euo pipefail 下，grep 无匹配（退出 1）会让整条管道的状态变 1，
  #      命令替换 n="$(...)" 随之失败 —— set -e 认为这是一条失败的命令，脚本直接退出。
  #      → 末尾补 || true，把状态吞掉。这是之前 set-repo.sh 静默返回 1 的原因。
  n="$(grep -o '__REPO__' "$f" 2>/dev/null | wc -l | tr -d ' ' || true)"
  n="${n:-0}"
  if [ "$n" -gt 0 ]; then
    sed_inplace "$f"
    echo "  $f  ← 替换 $n 处"
    total=$((total + n))
  fi
done

# ---------------------------------------------------------------- 防回归
# scripts/install.sh 与 scripts/bootstrap.sh 里各有一处「识别占位符是否还在」的哨兵，
# 必须写成「两个字符串字面量拼接」的形式（见 install.sh 的 SENTINEL 那一行）。
# 原因：上面的 sed 匹配的是连着的占位符，一旦哪个脚本把它写成连着的，替换之后
# 那一行就变成「拿真实仓库名和自己比」—— 于是连 --repo 传进来的正常值都会被清空。
#
# 这个 bug 真的发生过一次：CI 上 build-release 报「请用 --repo OWNER/REPO」，
# 而本地手动跑却完全正常（因为本地没跑过 set-repo.sh，字面量还是占位符）。
# 所以这里替换完立刻验一遍，坏了就硬失败，别让它跑到 CI 里才暴露。
broken=0
for f in scripts/install.sh scripts/bootstrap.sh; do
  [ -f "$f" ] || continue
  if ! grep -q 'RE""PO' "$f"; then
    echo "❗ ${f} 里的占位符哨兵被 sed 替换破坏了。" >&2
    echo "   它必须写成两段字符串拼接的形式（照着 scripts/install.sh 的 SENTINEL 那行写），" >&2
    echo "   否则真实仓库名会被当成占位符拒掉，CI 里会报「请用 --repo」。" >&2
    broken=1
  fi
done
if [ "$broken" -ne 0 ]; then
  exit 1
fi

echo
if [ "$total" -eq 0 ]; then
  echo "ℹ️  没有发现 __REPO__ 占位符（可能已经设置过了）。"
else
  echo "✅ 共替换 $total 处，仓库地址已设为 $REPO"
fi

# CI 里（.github/workflows/build-release.yml 会带着 $REPO 调这个脚本）不需要
# 「接下来你自己 commit / push」的提示 —— 那边是自动化跑的，打出来只会让人误会。
if [ -n "${CI:-}" ]; then
  exit 0
fi

echo
echo "接下来："
echo "  1) git add -A && git commit -m 'set repo' && git push"
echo "  2) 到 GitHub 仓库 Settings → Actions → General，把 Workflow permissions"
echo "     设为 Read and write，并勾选 Allow GitHub Actions to create and approve pull requests"
echo "  3) （可选）想启用 LLM 兜底翻译，在 Settings → Secrets 里加 LLM_API_KEY"
echo "  4) 手动跑一次 Actions → Sync upstream translations"
