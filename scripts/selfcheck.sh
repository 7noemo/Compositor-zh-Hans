#!/usr/bin/env bash
#
# 仓库自检 —— 提交 / 推送之前跑一遍，把能提前发现的坑都拦住。
#
#   bash scripts/selfcheck.sh
#   bash scripts/selfcheck.sh --src /path/to/上游源码      # 额外做覆盖率检查
#   bash scripts/selfcheck.sh --min-coverage 80
#
# 检查项：
#    1. 所有 Python 工具语法正常
#    2. shell 雷区 lint（$VAR 后跟中文、set -e 下的失败命令替换 等）
#    3. 所有 shell 脚本语法正常（bash -n）
#    4. 语言包通过 check-strings.py（格式、重复键、占位符一致性、
#       key 禁止带序号 %1$@ —— SwiftUI 运行时不会生成这种 key）
#       另外强制跑一遍「纯 Python 兜底语法检查」：Mac 有 plutil、Linux CI 没有，
#       两边判得不一样就是「本地绿、CI 红」，必须在这里先发现
#    5. 安装 / 还原脚本的关键逻辑（哨兵完好、参数守卫、会拆旧方案的自动汉化守护）
#       —— 全静态，无副作用
#    6. 打包脚本能真的产出 zip、含语言包、非 ASCII 名带 UTF-8 标志位、包名纯 ASCII
#    7. Release 说明能生成
#    8. workflow YAML 能解析
#    9. Release 附件名必须是纯 ASCII（GitHub 会改写非 ASCII 附件名）
#   10. （可选 --src）拿上游源码做**精确**覆盖率：
#       10.1 覆盖率不能低于阈值
#       10.2 缺口门禁按 CI 的宽松模式跑（有缺口只警告记账、不红），
#            另外用**合成数据**验证严格模式真的会在有真缺口时退出码 1
#            —— 直接跑宽松模式是永远通过的，不这么测就等于没查
#       10.3 提示表自动维护工具（sync_hints.py）能跑通
#       10.4 孤儿 key 清理工具（prune_obsolete.py）能跑通
#       10.5 四个工具都复用 analyze_coverage 里的插值算法 ——
#            一旦抄成两份，必然又出「本地绿、CI 红」
#
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SELF_DIR/.." && pwd)"
cd "$ROOT"

SRC_ARG=""
# 阈值针对「外挂可翻译文案」口径（A 类）。这个数字本来就该接近 100%，
# 因为剩下翻不了的根本不在分母里（它们属于 B 类）。
MIN_COVERAGE=99

while [ $# -gt 0 ]; do
  case "$1" in
    --src) [ $# -ge 2 ] || { echo "--src 后面要跟目录" >&2; exit 2; }
           SRC_ARG="$2"; shift 2 ;;
    --min-coverage) [ $# -ge 2 ] || { echo "--min-coverage 后面要跟数字" >&2; exit 2; }
           MIN_COVERAGE="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：${1}" >&2; exit 2 ;;
  esac
done

FAILED=0
ok()   { printf '  \033[32m✅\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m❌\033[0m %s\n' "$*"; FAILED=1; }
warn() { printf '  \033[33m⚠️\033[0m %s\n' "$*"; }
head1(){ printf '\n\033[1m%s\033[0m\n' "$*"; }

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=/usr/bin/python3
command -v "$PY" >/dev/null 2>&1 || { echo "找不到 python3" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/compositor-selfcheck.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

printf '\033[1m==== Compositor 简体中文语言包 · 仓库自检 ====\033[0m\n'

# ---------------------------------------------------------------- 1. Python 语法
head1 "1. Python 工具语法"
n=0
for f in scripts/tools/*.py; do
  [ -f "$f" ] || continue
  if "$PY" -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$f" 2>/dev/null; then
    n=$((n + 1))
  else
    bad "语法错误：${f}"
    "$PY" -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$f" 2>&1 | tail -3 | sed 's/^/     /' || true
  fi
done
[ "$n" -gt 0 ] && ok "${n} 个 tools/ 下的 Python 文件语法正常"

# ---------------------------------------------------------------- 2. shell 雷区
head1 "2. shell 雷区 lint"
if [ -f scripts/tools/lint-shell.py ]; then
  if "$PY" scripts/tools/lint-shell.py . > "$WORK/lint.out" 2>&1; then
    ok "没有 A 类雷区"
  else
    # lint 对「注释里的反例」不误报，所以这里报出来的都是真的要改
    bad "发现 A 类雷区（会在 macOS bash 3.2 上崩）："
  fi
  # B 类只告警、不影响退出码，但**必须打出来**：
  # 之前这里只在失败分支打印 lint.out，于是没有 A 类错误时
  # B 类警告被整份丢进临时目录，等于白查。
  if grep -q '⚠️' "$WORK/lint.out" 2>/dev/null; then
    printf '  \033[33m⚠️\033[0m B 类提示（pipefail 下可能静默终止，建议加 || true）：\n'
    grep '⚠️' "$WORK/lint.out" | sed 's/^/     /'
  fi
  if [ -s "$WORK/lint.out" ] && grep -q '❌' "$WORK/lint.out"; then
    grep -A1 '❌' "$WORK/lint.out" | sed 's/^/     /'
  fi
else
  warn "缺少 scripts/tools/lint-shell.py，跳过"
fi

# ---------------------------------------------------------------- 3. shell 语法
head1 "3. shell 语法"
syntax_bad=0
for f in scripts/*.sh 一键安装语言包.command 一键还原官方版.command; do
  [ -f "$f" ] || continue
  if ! bash -n "$f" 2>"$WORK/syntax.out"; then
    bad "语法错误：${f}"
    sed 's/^/     /' "$WORK/syntax.out"
    syntax_bad=1
  fi
done
[ "$syntax_bad" -eq 0 ] && ok "全部 shell 脚本语法正常"

# ---------------------------------------------------------------- 4. 语言包
head1 "4. 语言包"
PACK="zh-Hans.lproj/Localizable.strings"
if [ -s "$PACK" ]; then
  CNT="$(grep -c '^"' "$PACK" || true)"
  ok "语言包存在，${CNT} 条词条"
  if "$PY" scripts/tools/check-strings.py > "$WORK/chk.out" 2>&1; then
    ok "check-strings.py 通过"
  else
    bad "check-strings.py 未通过："
    tail -20 "$WORK/chk.out" | sed 's/^/     /'
  fi
  # 再兜一道：key 里不许出现带序号的格式符。
  # SwiftUI 的 LocalizedStringKey 在运行时只生成不带序号的格式符
  # （\(String)->%@，\(Int)->%lld，\(Double)->%lf，swiftc 反射实测），
  # 所以 "%1$@ × %2$@" 这种 key 永远查不到 —— 死条目。
  # 序号只允许写在**译文**里做参数重排。
  if grep -qE '^"[^"]*%[0-9]+\$[^"]*"[[:space:]]*=' "$PACK"; then
    bad "语言包 key 里有带序号的格式符（%1\$@ 这种），运行时永远查不到："
    grep -nE '^"[^"]*%[0-9]+\$[^"]*"[[:space:]]*=' "$PACK" | head -5 | sed 's/^/     /'
  else
    ok "语言包 key 没有带序号的格式符"
  fi

  # 4.4 纯 Python 兜底语法检查必须独立通过。
  #     Mac 上有 plutil，本地走的是权威那一版；CI 跑在 Linux 上没有 plutil，
  #     走的是纯 Python 那一版。两边判得不一样就是「本地绿、CI 红」——
  #     踩过一次：块注释的续行不以 /* 或 * 开头（以中文开头、行尾才写 */），
  #     旧版只按行首判断，把它当非法词条。
  #     现在实现只在 tools/strings_syntax.py 里有一份，这里强制它单独跑一遍，
  #     把「本地看不到的分歧」挡在提交之前。
  if STRINGS_LINT_FORCE_PY=1 "$PY" -c "
import sys
sys.path.insert(0, 'scripts/tools')
import strings_syntax as s
ok, detail = s.lint_strings('${PACK}', force_python=True)
print(detail)
raise SystemExit(0 if ok else 1)
" > "$WORK/pylint.out" 2>&1; then
    ok "纯 Python 兜底语法检查也通过（CI 在 Linux 上没有 plutil，走的就是这一版）"
  else
    bad "纯 Python 兜底语法检查未通过 —— 本地有 plutil 会掩盖它，CI 必炸："
    sed 's/^/     /' "$WORK/pylint.out"
  fi

  # 4.5 两个工具都必须真的用上公共实现，不许再各抄一份。
  if grep -qE '^\s*import strings_syntax' scripts/tools/check-strings.py &&
     grep -qE '^\s*import strings_syntax' scripts/tools/merge_translations.py; then
    ok "check-strings / merge_translations 都复用 strings_syntax.py"
  else
    bad "有工具没有 import strings_syntax —— 语法检查又会被抄成两份并产生分歧"
  fi
else
  bad "语言包不存在：${PACK}"
fi

# ---------------------------------------------------------------- 5. 脚本关键逻辑
head1 "5. 安装 / 还原脚本关键逻辑"

# 5.1 占位符哨兵必须写成两段拼接 —— 否则 set-repo.sh 的 sed 会把「识别占位符
#     的那一行」也替换掉，导致真实仓库名被当成占位符拒掉（CI 上踩过）。
if grep -q 'RE""PO' scripts/install.sh 2>/dev/null; then
  ok "install.sh 的占位符哨兵写法正确（两段拼接）"
else
  bad "install.sh 里的哨兵必须写成两段拼接，见文件里的 SENTINEL 那行"
fi

# 5.2 未替换占位符时必须有友好拦住。
#     这里**只做静态检查**，绝不真的调用 install.sh —— 那是会动
#     /Applications/Compositor.app 的操作，自检不能有副作用。
if grep -q '还没配置仓库地址' scripts/install.sh 2>/dev/null && \
   grep -q 'RE""PO' scripts/install.sh 2>/dev/null; then
  ok "占位符守卫就位（静态检查：哨兵 + 提示文案）"
else
  bad "install.sh 缺少占位符守卫，或哨兵写法不对"
fi

# 5.3 对不存在的 app 路径必须干脆报错 —— 这条是安全的：
#     路径不存在会在第一个检查就退出，不会碰任何现有安装。
#     传 --repo 是为了绕开「还没跑 set-repo.sh」这一关，直达 app 路径检查。
if [ -f scripts/install.sh ]; then
  if bash scripts/install.sh --repo selfcheck/local --app "$WORK/不存在的.app" --yes > "$WORK/app.out" 2>&1; then
    bad "对一个不存在的 app 路径，install.sh 居然返回成功"
  else
    if grep -q '指定的 app 不存在' "$WORK/app.out"; then
      ok "app 路径不存在时能正确报错"
    else
      warn "app 路径不存在时报错文案不明确："
      tail -3 "$WORK/app.out" | sed 's/^/     /'
    fi
  fi
fi

# 5.4 还原脚本的同名安全检查
if [ -f scripts/restore.sh ]; then
  if bash scripts/restore.sh --app "$WORK/不存在的.app" --yes > "$WORK/rst.out" 2>&1; then
    bad "对一个不存在的 app 路径，restore.sh 居然返回成功"
  else
    # 注意用 grep -E：macOS 是 BSD grep，BRE 不支持 \|
    if grep -qE '指定的 app 不存在|没找到' "$WORK/rst.out"; then
      ok "restore.sh 对不存在的路径能正确报错"
    else
      warn "restore.sh 报错文案不明确："
      tail -3 "$WORK/rst.out" | sed 's/^/     /'
    fi
  fi
fi

# 5.4 仓库里不该再出现编译发行版的残留
#     注意两点：
#       * 把自己排除掉 —— 报错文案里就带着这几个词，不排除的话永远自匹配。
#       * 把 _upstream/ 排除掉 —— 那是 fetch-upstream.sh 拉下来的**上游源码**，
#         里面本来就有 xcodebuild/release.sh（上游自己就出 DMG），
#         不排除的话本地一拉源码自检就假红。
#     用 grep -E：macOS 是 BSD grep，BRE 的 \| 行为不可靠。
if grep -rqE 'localize_patch|xcodebuild|build-release' \
      --include='*.sh' --include='*.yml' --include='*.py' \
      --exclude='selfcheck.sh' \
      --exclude-dir='_upstream' --exclude-dir='build' \
      --exclude-dir='dist' --exclude-dir='.git' . 2>/dev/null; then
  bad "还能找到编译发行版的残留引用（localize_patch / xcodebuild / build-release）"
  grep -rnE 'localize_patch|xcodebuild|build-release' \
      --include='*.sh' --include='*.yml' --include='*.py' \
      --exclude='selfcheck.sh' \
      --exclude-dir='_upstream' --exclude-dir='build' \
      --exclude-dir='dist' --exclude-dir='.git' . 2>/dev/null | head -5 | sed 's/^/     /'
else
  ok "已无编译发行版残留"
fi

# 5.5 安装 / 还原脚本都必须能拆掉「旧方案留下的自动汉化守护」。
#     那边（第三方的注入式汉化包）会装一个 LaunchAgent，WatchPaths 盯着
#     /Applications，任何往那里装东西的动作都会唤醒它，它随即把旧版语言包
#     回写进 Compositor.app。后果极具迷惑性：还原官方版后几秒界面自己变回
#     中文，用户以为「官方版装不上了 / 装出来是半汉化的」。
#     纯静态检查，不碰用户机器。
LEGACY_LEAK=0
for f in scripts/install.sh scripts/restore.sh; do
  if ! grep -q 'com\.wonderassembly\.compositor\.hanhua' "$f" 2>/dev/null; then
    bad "${f} 缺少旧方案自动汉化守护的识别逻辑"
    LEGACY_LEAK=1
  fi
  if ! grep -q 'remove_legacy_watchdog' "$f" 2>/dev/null; then
    bad "${f} 没有调用 remove_legacy_watchdog（旧守护会把语言包抢回旧版）"
    LEGACY_LEAK=1
  fi
done
if [ "$LEGACY_LEAK" -eq 0 ]; then
  ok "两个脚本都会先拆掉旧方案的自动汉化守护"
fi

# ---------------------------------------------------------------- 6. 打包
head1 "6. 打包语言包"
if bash scripts/make-langpack.sh "0.0.0-selfcheck" "$WORK/dist" > "$WORK/pack.out" 2>&1; then
  ZIP="$WORK/dist/Compositor-zh-Hans-langpack-v0.0.0-selfcheck.zip"
  if [ -f "$ZIP" ]; then
    if unzip -l "$ZIP" 2>/dev/null | grep -q 'zh-Hans.lproj/Localizable.strings'; then
      ok "zip 产出正常，且包含 zh-Hans.lproj/Localizable.strings"
    else
      bad "zip 里没有语言包"
    fi
    # 6.2 压缩包名必须是**纯 ASCII**。
    #     它要当 GitHub Release 的附件名，而 GitHub 会「重命名带特殊字符、
    #     非 ASCII 字符的附件名」（官方文档 REST API → releases → assets 的
    #     Notes 一节）。曾经包名叫「Compositor-zh-Hans-语言包-v1.4.6.zip」，
    #     发上去被悄悄改成「Compositor-zh-Hans-.-v1.4.6.zip」；两个中文名的
    #     一键脚本更惨，双双被改成 default.command 撞名报 422，CI 卡了很久。
    BAD_ZIPNAME="$(LC_ALL=C ls "$WORK/dist" | LC_ALL=C grep '[^ -~]' || true)"
    if [ -n "$BAD_ZIPNAME" ]; then
      bad "产物里有非 ASCII 文件名（Release 附件名只接受 ASCII）："
      printf '%s\n' "$BAD_ZIPNAME" | sed 's/^/     /'
    else
      ok "压缩包名是纯 ASCII"
    fi
    # 6.3 zip 里要带着两个一键脚本 —— 只下 zip 的用户也能拿到完整一套。
    #     注意 zip **内部**文件名不受附件名限制，所以这里保留中文名。
    #     这里必须用 Python 读 zip，不能用 unzip -l：macOS 自带的 Info-ZIP
    #     打印非 ASCII 文件名时会走样（跟打包脚本踩的是同一个坑），
    #     grep 中文名会静默匹配不上，白白误报。
    MISSING="$("$PY" - "$ZIP" <<'PYM' || true
import sys, zipfile
need = ["一键安装语言包.command", "一键还原官方版.command", "说明.txt"]
with zipfile.ZipFile(sys.argv[1]) as z:
    have = {i.filename for i in z.infolist()}
print(" ".join(n for n in need if n not in have))
PYM
)"
    if [ -n "$MISSING" ]; then
      bad "zip 里缺少：${MISSING}"
    else
      ok "zip 内含两个一键脚本与说明.txt"
    fi
    # 6.4 非 ASCII 文件名必须带 UTF-8 标志位（general purpose bit 11）。
    #     曾经用 /usr/bin/zip 打包，它写原始 UTF-8 字节却不置这个标志位，
    #     结果 Windows 资源管理器把「说明.txt」显示成「Φ»┤µÿÄ.txt」。
    #     这条守卫就是为了让那个坑不能再回来。
    "$PY" - "$ZIP" > "$WORK/zipenc.out" 2>&1 <<'PYZ' || true
import sys, zipfile
bad = []
with zipfile.ZipFile(sys.argv[1]) as z:
    for i in z.infolist():
        if not i.filename.isascii() and not (i.flag_bits & 0x800):
            bad.append(i.filename)
        print(i.filename)
if bad:
    print("MISSING_UTF8_FLAG:" + ",".join(bad))
PYZ
    if grep -q '^MISSING_UTF8_FLAG:' "$WORK/zipenc.out"; then
      bad "zip 里有非 ASCII 文件名没带 UTF-8 标志位（Windows 上会显示成乱码）：$(sed -n 's/^MISSING_UTF8_FLAG://p' "$WORK/zipenc.out")"
    else
      ok "zip 内非 ASCII 文件名均带 UTF-8 标志位"
    fi
    # 6.5 zip 内的权限位：目录必须有 x（否则解压后进不去 zh-Hans.lproj），
    #     一键脚本必须有 x（否则双击跑不起来）。
    #     ZipInfo 的 external_attr 默认是 0o600 —— 第一版就是这么发的包，
    #     macOS 自带 unzip 解出来是 drw-------，手动安装那步直接卡死。
    "$PY" - "$ZIP" > "$WORK/zipperm.out" 2>&1 <<'PYM' || true
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    for i in z.infolist():
        mode = i.external_attr >> 16
        if i.is_dir() and not (mode & 0o100):
            print("PERM:目录缺 x 位（解压后进不去）  %s  模式=%s" % (i.filename, oct(mode)))
        elif i.filename.endswith(".command") and not (mode & 0o100):
            print("PERM:脚本缺执行位（双击跑不起来）  %s  模式=%s" % (i.filename, oct(mode)))
PYM
    if grep -q '^PERM:' "$WORK/zipperm.out"; then
      bad "zip 内权限有问题："
      sed -n 's/^PERM://p' "$WORK/zipperm.out" | sed 's/^/     /'
    else
      ok "zip 内目录可进入、一键脚本可执行"
    fi
  else
    bad "没找到产出的 zip"
  fi
else
  bad "make-langpack.sh 失败："
  tail -10 "$WORK/pack.out" | sed 's/^/     /'
fi

# ---------------------------------------------------------------- 7. Release 说明
head1 "7. Release 说明生成"
if "$PY" scripts/tools/make_release_notes.py --repo selfcheck/local --version 0.0.0 \
     > "$WORK/notes.md" 2>"$WORK/notes.err"; then
  # 说明里必须给出「Release 附件名 → 中文名」的对照，否则用户下载到
  # install-zh-Hans.command 会一脸茫然。
  if grep -q 'install-zh-Hans.command' "$WORK/notes.md" && \
     grep -q 'restore-official.command' "$WORK/notes.md"; then
    ok "说明文件生成正常（$(wc -l < "$WORK/notes.md" | tr -d ' ') 行）"
  else
    bad "说明文件里没写清 Release 附件名的中文对照"
  fi
else
  bad "make_release_notes.py 失败："
  tail -5 "$WORK/notes.err" | sed 's/^/     /'
fi

# ---------------------------------------------------------------- 8. YAML
head1 "8. workflow YAML"
if "$PY" -c 'import yaml' 2>/dev/null; then
  for f in .github/workflows/*.yml; do
    [ -f "$f" ] || continue
    if "$PY" -c "
import sys, yaml, pathlib
d = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text())
assert 'jobs' in d, 'no jobs'
print(len(d['jobs']))
" "$f" > "$WORK/y.out" 2>"$WORK/y.err"; then
      ok "${f}"
    else
      bad "${f} 解析失败："
      tail -3 "$WORK/y.err" | sed 's/^/     /'
    fi
  done
else
  warn "本机没有 PyYAML，跳过（CI 上会有）"
fi

# ------------------------------------------------ 9. Release 附件名（纯 ASCII）
head1 "9. Release 附件名"
# GitHub 会「重命名带特殊字符、非 ASCII 字符的附件名」（官方文档 REST API →
# releases → assets 的 Notes 一节），而且**不报错** —— 直到用户下载到一个叫
# default.command 的怪文件才发现。两个中文名还会被改写成同一个名字，
# 报 422 ReleaseAsset.name already exists 把整个发布步骤拖红。
# 这里把 workflow 里真正会变成附件的文件名抽出来，逐个断言是纯 ASCII。
WF=".github/workflows/sync-upstream.yml"
if [ -f "$WF" ]; then
  # 9.1 「组装发布物」那步 cp 进 dist/ 的名字
  ASSET_NAMES="$(grep -oE '"dist/[^"]*"' "$WF" | tr -d '"' | sed 's|^dist/||' | sort -u || true)"
  if [ -z "$ASSET_NAMES" ]; then
    warn "没在 ${WF} 里找到写入 dist/ 的文件名，本项检查可能失效"
  else
    BAD_A="$(printf '%s\n' "$ASSET_NAMES" | LC_ALL=C grep '[^ -~]' || true)"
    if [ -n "$BAD_A" ]; then
      bad "${WF} 里用作 Release 附件的名字含非 ASCII（GitHub 一定会改写）："
      printf '%s\n' "$BAD_A" | sed 's/^/     /'
    else
      ok "dist/ 附件名均为纯 ASCII：$(printf '%s' "$ASSET_NAMES" | tr '\n' ' ')"
    fi
  fi
  # 9.2 压缩包名（真正的字符来自 make-langpack.sh，第 6 项已单独把关）
  ZIP_DECL="$(grep -m1 -E '^[[:space:]]*ZIP=' "$WF" | sed 's/^[[:space:]]*ZIP=//' | tr -d '"' || true)"
  if [ -n "$ZIP_DECL" ]; then
    if printf '%s' "$ZIP_DECL" | LC_ALL=C grep -q '[^ -~]'; then
      bad "workflow 里的压缩包名含非 ASCII：${ZIP_DECL}"
    else
      ok "workflow 的压缩包名是纯 ASCII：${ZIP_DECL}"
    fi
  else
    warn "没找到 ZIP= 声明，跳过"
  fi
  # 9.3 上传之后必须有反查 —— GitHub 悄悄改名时，没有反查就完全发现不了
  if grep -q '核对附件名' "$WF"; then
    ok "workflow 有「附件名核对」步骤"
  else
    bad "workflow 缺少附件名核对：GitHub 改写附件名不报错，必须有反查"
  fi
else
  warn "找不到 ${WF}，跳过"
fi

# ---------------------------------------------------------------- 10. 覆盖率
head1 "10. 覆盖率（外挂方案口径）"

# 没传 --src 时，本地若已有 fetch-upstream.sh 拉下来的源码就直接用它。
# 覆盖率 + 缺口检查是这套方案最重要的一道闸，静默跳过等于没查 ——
# 曾经因此让「有译文却显示英文」的条目漏过很久，所以宁可自动猜一次并说明。
if [ -z "$SRC_ARG" ] && [ -d "_upstream" ]; then
  SRC_ARG="_upstream"
  warn "未传 --src，自动使用现有的 _upstream/（想指定别的加 --src <目录>）"
fi

if [ -n "$SRC_ARG" ]; then
  if [ -d "$SRC_ARG" ]; then
    if "$PY" scripts/tools/analyze_coverage.py "$SRC_ARG" \
         --pack "$PACK" --json build/coverage.json --show-b 6 > "$WORK/cov.out" 2>&1; then
      sed 's/^/     /' "$WORK/cov.out"
      PCT="$("$PY" -c "
import json;print(json.load(open('build/coverage.json'))['translatable']['coverage_percent'])" 2>/dev/null || echo 0)"
      if "$PY" -c "import sys; sys.exit(0 if float('$PCT') >= float('$MIN_COVERAGE') else 1)"; then
        ok "外挂可翻译文案覆盖率 ${PCT}% ≥ ${MIN_COVERAGE}%"
      else
        bad "覆盖率 ${PCT}% 低于阈值 ${MIN_COVERAGE}% —— 有新增文案没翻？"
      fi

      # 10.2 缺口门禁。
      #      2026-10-10 起 CI 改用「宽松模式」：有未译文案只记账（写
      #      build/gaps.json、开 Issue、写进 Release 说明），**不再中断流水线** ——
      #      以前有缺口就退出码 1，于是上游加一条新文案就让整条流水线永久卡死等人修。
      #      副作用是宽松模式永远返回 0，直接跑它等于没查。所以这里：
      #        a) 先按 CI 的方式跑一遍（其实永远通过，但会把缺口清单打出来）
      #        b) 再用**合成数据**验证严格模式确实会在有真缺口时退出码 1
      if "$PY" scripts/tools/check-coverage-gap.py build/coverage.json \
           > "$WORK/gap.out" 2>&1; then
        sed 's/^/     /' "$WORK/gap.out"
        GAPN="$("$PY" -c "
import json;print(json.load(open('build/gaps.json'))['missing_contentful'])" 2>/dev/null || echo 0)"
        if [ "$GAPN" = "0" ]; then
          ok "A 类缺口只剩无实际内容的文案"
        else
          warn "有 ${GAPN} 条带实际内容的缺口 —— 不拦你，CI 会照常发布并记账（见上）"
        fi
      else
        sed 's/^/     /' "$WORK/gap.out"
        bad "缺口检查脚本本身出错（不是「有缺口」，是工具挂了）—— 见上"
      fi

      # 10.2b 合成数据测严格模式：有真缺口必须返回 1，只有符号缺口必须返回 0。
      #       不测这个的话，宽松模式改错了（比如忘了 return 1）永远发现不了。
      "$PY" -c "
import json
json.dump({'translatable': {'distinct_strings': 10, 'covered': 8,
                            'coverage_percent': 80.0},
           'missing_keys': ['', '·', 'Some Real Gap'],
           'hints': {'loaded': 0, 'stale': [], 'unhinted_literals': []}},
          open('$WORK/cov-real-gap.json', 'w'), ensure_ascii=False)
json.dump({'translatable': {'distinct_strings': 10, 'covered': 9,
                            'coverage_percent': 90.0},
           'missing_keys': ['', '·'],
           'hints': {'loaded': 0, 'stale': [], 'unhinted_literals': []}},
          open('$WORK/cov-symbol-only.json', 'w'), ensure_ascii=False)
"
      RC1=0
      "$PY" scripts/tools/check-coverage-gap.py "$WORK/cov-real-gap.json" \
        --strict --gaps-out "$WORK/g1.json" >/dev/null 2>&1 || RC1=$?
      RC0=0
      "$PY" scripts/tools/check-coverage-gap.py "$WORK/cov-symbol-only.json" \
        --strict --gaps-out "$WORK/g0.json" >/dev/null 2>&1 || RC0=$?
      if [ "$RC1" -eq 1 ] && [ "$RC0" -eq 0 ]; then
        ok "严格模式判定正确（有真缺口=1，只有符号缺口=0）"
      else
        bad "严格模式判定不对：有真缺口应得 1 实际 ${RC1}，只有符号缺口应得 0 实际 ${RC0}"
      fi
      # 宽松模式对同一份「有真缺口」的数据必须放行，否则 CI 又会被卡住
      RCW=0
      "$PY" scripts/tools/check-coverage-gap.py "$WORK/cov-real-gap.json" \
        --gaps-out "$WORK/g1.json" >/dev/null 2>&1 || RCW=$?
      if [ "$RCW" -eq 0 ]; then
        ok "宽松模式对未译缺口不拦截（CI 不会被卡住）"
      else
        bad "宽松模式居然退出码 ${RCW} —— 那 CI 又会因为缺口永久卡死"
      fi

      # 10.3 / 10.4 两个自动维护工具必须能跑通（都走 --dry-run，无副作用）
      if "$PY" scripts/tools/sync_hints.py build/coverage.json --dry-run \
           > "$WORK/hints.out" 2>&1; then
        ok "提示表自动维护工具能跑通（$(grep -c . "$WORK/hints.out") 行输出）"
      else
        bad "sync_hints.py 跑不通 —— 提示表失效又会变成永久红："
        tail -8 "$WORK/hints.out" | sed 's/^/     /'
      fi
      if "$PY" scripts/tools/prune_obsolete.py build/coverage.json --dry-run \
           > "$WORK/prune.out" 2>&1; then
        ok "孤儿 key 清理工具能跑通（$(grep -c . "$WORK/prune.out") 行输出）"
      else
        bad "prune_obsolete.py 跑不通："
        tail -8 "$WORK/prune.out" | sed 's/^/     /'
      fi

      # 10.5 插值 key 的算法只能有一份 —— 抄成两份必然分歧（踩过一次：
      #      merge_translations / check-strings 各抄一份 .strings 语法检查，
      #      结果「本地 plutil 绿、Linux CI 红」，查了半天）。
      #      断言的是「都从 analyze_coverage 里取」这个不变量，
      #      而不是某个具体函数名 —— extract_strings 用 key_variants、
      #      sync_hints 用 split_interpolations，各自取的符号本来就不同。
      MISSING_IMPORT=""
      for f in extract_strings.py translate_missing.py sync_hints.py prune_obsolete.py; do
        if ! grep -q 'analyze_coverage' "scripts/tools/${f}" 2>/dev/null; then
          MISSING_IMPORT="${MISSING_IMPORT} ${f}"
        fi
      done
      if [ -z "$MISSING_IMPORT" ]; then
        ok "四个工具都复用 analyze_coverage（插值 key 的算法只有一份）"
      else
        bad "这些工具没复用 analyze_coverage，可能自己抄了一份：${MISSING_IMPORT}"
      fi
    else
      bad "analyze_coverage.py 失败："
      tail -10 "$WORK/cov.out" | sed 's/^/     /'
    fi
  else
    warn "目录不存在，跳过覆盖率检查：${SRC_ARG}"
  fi
else
  warn "未传 --src 且没有 _upstream/，跳过覆盖率检查（先跑 bash scripts/fetch-upstream.sh）"
fi

# ---------------------------------------------------------------- 收尾
printf '\n'
if [ "$FAILED" -eq 0 ]; then
  printf '\033[32m==== ✅ 全部检查通过 ====\033[0m\n'
else
  printf '\033[31m==== ❌ 有检查未通过，见上 ====\033[0m\n'
fi
exit "$FAILED"
