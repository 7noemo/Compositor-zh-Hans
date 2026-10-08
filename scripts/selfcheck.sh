#!/usr/bin/env bash
#
# 本地/CI 自检：在上游源码上打完补丁后，检查补丁本身有没有把代码改坏。
#
#   scripts/selfcheck.sh [--src DIR]
#
# 检查项
#   1. 各 Python 工具语法正常
#   2. 补丁可重复执行（幂等）—— 第二遍不应再产生任何改动
#   3. 补丁后 146 个 .swift 全部能通过 swiftc -parse（真正的语法校验）
#   4. 语言包通过 check-strings.py
#   5. 覆盖率不低于阈值
#
# 这一步的价值：CI 里它比完整编译快得多，能在几分钟内拦下
# 「上游改了写法导致 Rule 落空」或「补丁把括号改坏了」这类问题。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SRC_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --src) [ $# -ge 2 ] || { echo "--src 后面要跟上上游源码目录" >&2; exit 2; }
           SRC_ARG="$2"; shift 2 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

PY="${PYTHON:-python3}"
MIN_COVERAGE="${MIN_COVERAGE:-85}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/compositor-selfcheck.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail=0
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
bad()  { printf '\033[31m   ❌ %s\033[0m\n' "$*"; fail=1; }
ok()   { printf '\033[32m   ✅ %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- 1. 工具语法
step "检查工具链语法"
for f in scripts/tools/*.py; do
  if "$PY" -c "import ast,sys;ast.parse(open('$f',encoding='utf-8').read())"; then
    ok "$f"
  else
    bad "$f 语法错误"
  fi
done

# ---------------------------------------------------------------- 1b. shell 雷区
# 这一项是踩坑之后补的：macOS 自带的 bash 是 3.2，会把「$VAR 后面紧跟的中文/全角标点」
# 吞进变量名（$TARGET（ → 变量 `TARGET（` → unbound variable 直接终止脚本）。
# 而这种写法在 Linux 的 bash 5 上完全正常，所以只有用户机器上才炸，CI 看不出来。
# 详见 scripts/tools/lint-shell.py 的头部注释。
step "检查 shell 脚本雷区"
if "$PY" scripts/tools/lint-shell.py .; then
  ok "shell 脚本无 A 类雷区"
else
  bad "shell 脚本存在 A 类雷区（会在 macOS bash 3.2 上崩溃，见上）"
fi

# ---------------------------------------------------------------- 2. 准备源码
step "准备带补丁的源码"
if [ -n "$SRC_ARG" ]; then
  [ -d "$SRC_ARG/Compositor" ] || { bad "不是 Compositor 源码目录：$SRC_ARG"; exit 1; }
  cp -R "$SRC_ARG" "$WORK/a"
else
  [ -d "_upstream/Compositor" ] || {
    echo "   本地没有 _upstream/，先跑 scripts/bootstrap.sh" >&2
    exit 2
  }
  cp -R "_upstream" "$WORK/a"
fi

REPO="${GITHUB_REPOSITORY:-selfcheck/local}"
"$PY" scripts/tools/localize_patch.py "$WORK/a" --repo "$REPO" >/dev/null
ok "补丁应用完成"

# ---------------------------------------------------------------- 3. 幂等
step "验证补丁幂等（第二遍不应产生改动）"
cp -R "$WORK/a" "$WORK/b"
"$PY" scripts/tools/localize_patch.py "$WORK/b" --repo "$REPO" >/dev/null
if diff -rq "$WORK/a" "$WORK/b" >/dev/null; then
  ok "幂等"
else
  bad "第二遍又改了东西，补丁不幂等："
  diff -rq "$WORK/a" "$WORK/b" | head -10
fi

# ---------------------------------------------------------------- 4. 语法
step "swiftc -parse 语法校验"
if ! command -v swiftc >/dev/null 2>&1; then
  echo "   ⏭  没有 swiftc，跳过（CI 的 macOS runner 上会跑）"
else
  bad_files=0
  total=0
  while IFS= read -r f; do
    total=$((total + 1))
    if ! swiftc -parse "$f" >/dev/null 2>&1; then
      bad_files=$((bad_files + 1))
      bad "语法错误：$f"
      swiftc -parse "$f" 2>&1 | head -4 | sed 's/^/      /'
    fi
  done < <(find "$WORK/a/Compositor" -name '*.swift' | sort)
  [ "$bad_files" -eq 0 ] && ok "$total 个 Swift 文件全部通过"
fi

# ---------------------------------------------------------------- 5. 语言包
step "校验语言包"
if "$PY" scripts/tools/check-strings.py > "$WORK/check.log" 2>&1; then
  ok "$(grep -o '共 [0-9]* 条词条' "$WORK/check.log" | head -1)"
else
  bad "check-strings.py 未通过"
  tail -20 "$WORK/check.log" | sed 's/^/      /'
fi

# ---------------------------------------------------------------- 6. 覆盖率
step "统计覆盖率"
"$PY" scripts/tools/extract_strings.py "$WORK/a" > "$WORK/extract.log" 2>&1 || true
tail -8 "$WORK/extract.log" | sed 's/^/   /'
PCT="$("$PY" -c "import json;print(json.load(open('build/stats.json'))['coverage_percent'])" 2>/dev/null || echo 0)"
if [ -z "$PCT" ]; then PCT=0; fi
if awk "BEGIN{exit !($PCT >= $MIN_COVERAGE)}"; then
  ok "覆盖率 $PCT% ≥ 阈值 $MIN_COVERAGE%"
else
  bad "覆盖率 $PCT% < 阈值 $MIN_COVERAGE%"
fi

# ---------------------------------------------------------------- 结论
printf '\n'
if [ "$fail" -eq 0 ]; then
  printf '\033[32m✅ 自检全部通过\033[0m\n'
else
  printf '\033[31m❌ 自检未通过，请修好再出包\033[0m\n'
fi
exit "$fail"
