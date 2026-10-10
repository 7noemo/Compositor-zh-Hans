#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「待译清单」自动补齐译文：术语表优先，LLM 兜底。

输入：
    build/to-translate.tsv       extract_strings.py 的产物（key <TAB> 空 <TAB> 来源）
    build/coverage.json          analyze_coverage.py 的产物 —— **用它把清单筛成 A 类**
    zh-Hans.lproj/Localizable.strings   已有译文（最高权威）
    translations/curated.tsv    人工校对译文
    translations/glossary.tsv   术语表
    translations/auto.tsv       上一轮自动产出的译文（人工复核后可留可删）

输出：
    translations/auto.tsv       本轮自动补齐的译文（会被 merge_translations.py 合并进语言包）

翻不了的直接跳过，不留待办（2026-10-10 起）
------------------------------------------
术语表没命中、LLM 也没处理掉的文案，**只打印条数，不写待办清单、不开 Issue**。
理由：这批东西要么是外挂方案本来就翻不了的（B 类），要么是模型处理不了的长尾；
把它们攒成一份「等人来认领」的清单，等于给整条流水线留了一条永远需要人工的尾巴 ——
上游每发一版就要有人去看一眼，那正是这套自动化要拆掉的东西。
想自己补译的时候再补就行：把 key<TAB>译文 加进 translations/curated.tsv（最高权威）。

为什么必须按 A 类过滤（2026-10-10 加）
--------------------------------------
extract_strings.py 走的是**全量口径**：把源码里所有像人话的字面量都捞出来。
那份清单里混着两类翻不了的东西：

  * B 类 —— 先赋给 String 变量再进视图（Text(title)、.help(help)、
    NSMenuItem(title: …)…）。SwiftUI 不查表，放语言包里也不生效。
  * 源码片段噪音 —— ' by 10'、' EV'、' : session.shapeKind == .rectangle ? ' 之类。

不筛的话，一旦配了 LLM_API_KEY，模型会把它们也翻一遍塞进语言包 ——
每次同步平白多一两百条永远查不到的死条目，日志也会被人造噪音淹没。
所以现在默认只翻 analyze_coverage.py 认定的「A 类里还缺译文」的那批。
想恢复全量行为加 --no-filter。

术语表优先的三级命中
--------------------
  1. 归一化后精确命中（大小写、引号、破折号、空白差异都忽略）
  2. 占位符骨架命中：把 key 里的 %@ / %lld / %d … 抽象成 ⟨0⟩⟨1⟩，
     与词典里骨架相同的词条对上就沿用它的译文（占位符位置可不同）
  3. LLM 兜底：把剩下的整批发给模型，要求输出 JSON，并附上术语表作为用词约束

安全
----
  * 默认不联网。只有显式设置 LLM_API_KEY（或 --llm）才会发起请求，且内容只有界面英文短语。
  * 永远不翻译的东西由 GUARD 规则拦下（PSD 格式常量、纯数值、专有设备名等）。

离线自检
--------
    python3 scripts/tools/translate_missing.py --selftest-llm

不联网、不需要 API Key，用合成响应把整条链路跑一遍（参数接口 / 请求体 /
响应解析 / 幻觉 key 与占位符的三道拦截）。selfcheck.sh 会跑它。

为什么必须有它：这个模块的 LLM 路径曾经在**首次调用就抛 ValueError**，而异常
类型恰好躺在调用处的 except 列表里 → 静默跳过一整批。仓库当时没配 key，
这段代码从没执行过，所以连 CI 都发现不了。见 llm_translate / keys_ok 的注释。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(ROOT, "build")
PACK = os.path.join(ROOT, "zh-Hans.lproj", "Localizable.strings")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用「插值 -> 格式串」的候选生成：既用来把清单筛成 A 类，
# 也用来保证给出的 key 形式与运行时一致（提示表优先）。
from analyze_coverage import HINTS, HINTS_PATH, key_variants, load_hints  # noqa: E402

HINTS.clear()
HINTS.update(load_hints(HINTS_PATH))

PLACEHOLDER = re.compile(
    r'%(?:\d+\$)?[-+ #0]*(?:\d+)?(?:\.\d+)?(?:hh|h|ll|l|q|L|z|j|t)?[@diouxXeEfgGaAcsp]')

# ---------------------------------------------------------------- 不译清单
# PSD / TIFF 里的 4 字符格式常量、二进制标记
PSD_CONST = re.compile(r'^(?:8BIM|8BPS|8B64|[A-Z][a-z]?\d{2}|[A-Z]{1,2}[a-z]{2,3})$')
# 苹果设备型号：这是商品名，中文版也不翻
DEVICE = re.compile(r'^(?:MacBook|Mac Studio|Mac Pro|Mac mini|iMac|iPhone|iPad|'
                    r'Studio Display|Pro Display|Apple)\b')
# 只有数字、符号、单位
NUMERICISH = re.compile(r'^[%\d\s.,:×°–—\-/()\[\]+]*$')
# 代码片段、Swift 关键字、路径、URL、UTI
CODEISH = re.compile(r'^(?:NS|CG|CI|UTType|k[A-Z]|com\.|https?:|\.{1,2}/)|'
                     r'\{[^}]*\}|->|==|!=|\?\?|\.\w+\(')
# 形如 "\(...)" 的插值碎片（extract 的切分残留），不是给人看的
INTERP_FRAG = re.compile(r'^[^A-Za-z]*\\\(|\\\)[^A-Za-z]*$')


def is_untranslatable(s, never=None):
    if never and norm(s) in never:
        return True
    if not re.search(r'[A-Za-z]', s):
        return True
    if len(s.strip()) < 2:
        return True
    if PSD_CONST.match(s) and ' ' not in s:
        return True
    if DEVICE.match(s):
        return True
    if NUMERICISH.match(s):
        return True
    if CODEISH.search(s):
        return True
    if INTERP_FRAG.search(s):
        return True
    # 单字母 / 双字母的通道名与单位：R / G / B / X / Y / px / px/s
    if re.fullmatch(r'[A-Za-z]{1,3}(?:/[A-Za-z]{1,3})?', s):
        return True
    return False


def load_never():
    """永不翻译清单：每行一个 key，# 注释。归一化后比对。"""
    path = os.path.join(ROOT, "translations", "never-translate.txt")
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            out.add(norm(line.strip()))
    return out


# ---------------------------------------------------------------- 归一化
QUOTES = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'",
                        '–': '-', '—': '-', '−': '-'})


def norm(s):
    """把不影响语义的排版差异抹平，用于术语表命中。"""
    s = s.translate(QUOTES)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^\s*[.·]\s*', '', s)
    return s.lower()


def skeleton(s):
    """把占位符抽象成序号骨架：'Hide %@' -> ('hide ⟨⟩', ['%']×1)。"""
    return norm(PLACEHOLDER.sub('⟨⟩', s))


def has_placeholder(s):
    return bool(PLACEHOLDER.search(s))


# ---------------------------------------------------------------- 词典装载
ENTRY = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', re.M)


def _unescape(s):
    return (s.replace('\\"', '"').replace('\\n', "\n").replace('\\t', "\t")
             .replace('\\\\', "\\"))


def load_strings_pack(path):
    """读语言包。纯 Python，任何平台一致（同步流水线跑在 Linux 上）。"""
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8-sig").read()
    return {_unescape(m.group(1)): _unescape(m.group(2)) for m in ENTRY.finditer(text)}


def load_tsv(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                continue
            key, val = line.split("\t", 1)
            key, val = key.strip(), val.strip()
            if key and val:
                rows[key] = val
    return rows


def build_dict():
    """返回 (按归一化 key 的词典, 按骨架的词典)。后加载的覆盖先加载的。"""
    sources = [
        ("内置语言包", load_strings_pack(PACK)),
        ("术语表", load_tsv(os.path.join(ROOT, "translations", "glossary.tsv"))),
        ("自动产出", load_tsv(os.path.join(ROOT, "translations", "auto.tsv"))),
        ("人工校对", load_tsv(os.path.join(ROOT, "translations", "curated.tsv"))),
    ]
    exact, skel = {}, {}
    for name, rows in sources:
        for k, v in rows.items():
            if not v:
                continue
            nk = norm(k)
            exact[nk] = v
            skel.setdefault(skeleton(k), (k, v))
    return exact, skel


# ---------------------------------------------------------------- LLM 兜底
SYSTEM_PROMPT = """你是专业的软件界面本地化译者，把 macOS 图像编辑器 Compositor 的英文界面文案翻译成简体中文。

硬性要求：
1. 用词必须与 Adobe Photoshop 简体中文版一致（图层、蒙版、选区、羽化、色阶、曲线、滤镜…）。
2. 保留所有占位符原样、原顺序、原类型：%@ %lld %d %f %1$@ 等一个字符都不能改，也不能增删。
   注意 %% 表示一个字面量百分号，翻译后必须仍是 %%。
3. 句末标点跟随中文习惯；圆括号内若是纯英文专名则保留英文。
4. 不要翻译：产品名（Compositor、Camera Raw）、快捷符号（⌘ ⌥ ⇧ ⌃）、单位（px、DPI、sRGB、RGBA）、
   文件名后缀、以及纯数字读数。
5. 译文里不要出现解释、注释、引号包裹或 Markdown。
6. 只输出 JSON 对象，键是英文原文，值是中文译文，不要任何其它文字。"""


def llm_translate(keys, api_key, base_url, model, glossary_hint, timeout=120):
    """keys: [界面文案, …] -> {key: 译文}。失败抛异常。

    ⚠️ 2026-10-10 修：这里收的是**纯字符串列表**。
    原先签名写的是 `items: [(key, 来源说明)]`、内部按 `for k, _ in items` 解包，
    而唯一的调用点传的是 `chunk = need_llm[i:i+batch]` —— need_llm 里存的就是
    key 字符串本身。于是**第一次调用就抛 `ValueError: too many values to unpack`**，
    而这个异常类型恰好躺在调用处的 except 列表里 → 被静默吞掉、整批跳过。
    配上 LLM_API_KEY 之前这段代码永远进不去，所以这个洞一直没人发现 ——
    也就是说「配了 key 依然全是英文，而且日志只说一句调用失败」。
    来源说明本来就没进提示词，索性把接口收成最简单的形式。
    """
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                "术语表（英文 = 中文，必须优先采用）：\n" + glossary_hint +
                "\n\n请翻译下面这批界面文案：\n" +
                json.dumps(list(keys), ensure_ascii=False, indent=1)},
        ],
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + api_key},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"].strip()
    content = re.sub(r'^```(?:json)?|```$', '', content, flags=re.M).strip()
    data = json.loads(content)
    return {k: v for k, v in data.items() if isinstance(v, str) and v.strip()}


# ---------------------------------------------------------------- 校验
def placeholders_ok(key, value):
    return sorted(PLACEHOLDER.findall(key)) == sorted(PLACEHOLDER.findall(value))


def keys_ok(wanted, mapping):
    """LLM 可能回传没请求过的 key、漏掉占位符，或干脆没翻成中文，全部拦下来。

    wanted: 这批请求的 key（字符串或列表）；mapping: 模型回传的 {key: 译文}。

    ⚠️ 2026-10-10 修：原先第一道判断是
        `if k not in {kk for kk, _ in mapping.items()}: continue`
    —— 恒为假（k 本来就取自 mapping.items()），等于没判。后果是模型幻觉出来的、
    根本没请求过的 key 会被原样收进 auto.tsv，再被 merge_translations 合并进
    语言包，成为永远查不到的死条目。改成跟**请求列表**比。
    """
    allowed = {wanted} if isinstance(wanted, str) else set(wanted)
    clean, rejected = {}, []
    for k, v in mapping.items():
        if k not in allowed:
            rejected.append((k, v, "不在请求列表里"))
            continue
        if not placeholders_ok(k, v):
            rejected.append((k, v, "占位符不一致"))
            continue
        if not re.search(r'[\u4e00-\u9fff]', v):
            rejected.append((k, v, "译文不含中文"))
            continue
        clean[k] = v
    return clean, rejected


def selftest_llm():
    """离线自检整条 LLM 链路：不联网、不需要 API Key。返回 0/1。

    为什么非要这个（2026-10-10 加）：
      `llm_translate` 曾经因为「参数传字符串列表、实现按元组解包」在**首次调用**
      就抛 ValueError，而该异常类型在调用处的 except 里 → 静默跳过一整批。
      当时仓库没配 LLM_API_KEY，这段代码从没执行过，所以任何检查都发现不了 ——
      包括 CI。想不重犯，就得有一条**不依赖 key、不依赖网络**的路径去跑它。

      合成一份假响应就够覆盖四个易错点：
        1) 参数接口（字符串列表 vs 元组列表）
        2) 请求体里确实带上了要翻的文案
        3) 响应解析（```json 围栏、非字符串值）
        4) keys_ok 的三道拦截（幻觉 key / 占位符丢失 / 没翻成中文）
    """
    keys = ["Halftone screen angle",
            "Rotate the canvas by %@ degrees",
            "Repeat the last filter %lld times"]
    # 模型「回话」：2 条合格 + 1 条吃掉占位符 + 1 条根本没请求过的 key
    canned = {
        "Halftone screen angle": "半调网屏角度",
        "Rotate the canvas by %@ degrees": "将画布旋转 %@ 度",
        "Repeat the last filter %lld times": "重复上一个滤镜次",   # 丢了 %lld
        "Totally made up key": "凭空出现的条目",                  # 幻觉
    }
    body = {
        "choices": [{"message": {
            "content": "```json\n" + json.dumps(canned, ensure_ascii=False) + "\n```"}}],
    }
    sent = []

    class _Resp(object):
        def read(self):
            return json.dumps(body).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _fake_urlopen(req, timeout=None):     # noqa: ARG001
        sent.append(req)
        return _Resp()

    real = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        got = llm_translate(keys, "selftest-key", "https://example.invalid/v1", "m", "")
    except Exception as exc:                  # noqa: BLE001
        print("   ❌ llm_translate 抛异常（接口或解析坏了）：%r" % (exc,))
        return 1
    finally:
        urllib.request.urlopen = real

    problems = []
    if len(sent) != 1:
        problems.append("应当恰好发 1 次请求，实际 %d 次" % len(sent))
    if sent:
        payload = sent[0].data.decode("utf-8")
        for k in keys:
            if k not in payload:
                problems.append("请求体里漏掉了 %r" % k)

    clean, rejected = keys_ok(keys, got)
    if sorted(clean) != sorted(keys[:2]):
        problems.append("合格译文应当只有前 2 条，实际 %r" % sorted(clean))
    if len(rejected) != 2:
        problems.append("应当拦下 2 条坏结果（丢占位符 + 幻觉 key），实际 %d 条"
                        % len(rejected))
    if "Totally made up key" in clean:
        problems.append("幻觉出来的 key 被放行了 —— auto.tsv 会污染语言包")

    if problems:
        for p in problems:
            print("   ❌ " + p)
        return 1
    print("   ✅ LLM 链路自检通过（接口 / 请求体 / 解析 / 三道拦截）")
    return 0


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todo", default=os.path.join(BUILD, "to-translate.tsv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "translations", "auto.tsv"))
    ap.add_argument("--batch", type=int, default=40, help="每次发给 LLM 的条数")
    ap.add_argument("--llm", action="store_true", help="即使没有 API Key 也尝试调用")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少条（调试用）")
    ap.add_argument("--coverage", default=os.path.join(BUILD, "coverage.json"),
                    help="analyze_coverage.py 的产物，用来把清单筛成 A 类")
    ap.add_argument("--no-filter", action="store_true",
                    help="不做 A 类过滤，按全量清单翻（会产生大量死条目）")
    ap.add_argument("--selftest-llm", action="store_true",
                    help="离线自检 LLM 调用链（不联网、不需要 key），返回 0/1")
    args = ap.parse_args()

    if args.selftest_llm:
        return selftest_llm()

    if not os.path.exists(args.todo):
        print(f"❌ 找不到待译清单 {args.todo}，请先运行 extract_strings.py", file=sys.stderr)
        return 1

    todo = []
    with open(args.todo, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key = line.split("\t")[0].strip()
            if key:
                todo.append(key)
    if args.limit:
        todo = todo[:args.limit]

    # ---- 筛成 A 类：全量清单里混着 B 类与源码噪音，翻了也不生效 ----
    if not args.no_filter:
        if os.path.exists(args.coverage):
            with open(args.coverage, encoding="utf-8") as fh:
                cov = json.load(fh)
            need = set()
            for lit in cov.get("missing_keys", []):
                need.add(lit)
                # A 类缺口在清单里是以「算出来的 key」形式出现的（含全部候选），
                # 所以把每条缺口文案的候选 key 也放进允许集合
                need.update(key_variants(lit))
            before = len(todo)
            todo = [k for k in todo if k in need]
            print(f"A 类过滤        : {before} 条 -> {len(todo)} 条"
                  f"（滤掉 {before - len(todo)} 条 B 类/噪音）")
        else:
            print(f"⚠️  找不到 {args.coverage}，无法筛成 A 类；"
                  f"先跑 analyze_coverage.py --json（或加 --no-filter 无脑全翻）")

    exact, skel = build_dict()
    never = load_never()
    print(f"待译条目        : {len(todo)}")
    print(f"词典规模        : 精确 {len(exact)} / 骨架 {len(skel)}")
    print(f"永不翻译清单    : {len(never)} 条")

    # 引擎状态：让「Secret 有没有送达运行器」在 CI 日志里一眼可见。
    # 为什么值得单独打一行：没配好 key 和「模型没给出合格结果」的表现**完全一样**
    # —— 都是静默跳过、什么都不说。不打出这一行，出了事只能靠猜。
    # 注意永远不要打印 key 本身，只报「配没配」和模型/地址。
    _key = os.environ.get("LLM_API_KEY", "").strip()
    _model = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()
    _base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    if _key:
        print(f"LLM 引擎        : 已配置 {_model} @ {_base}")
    else:
        print("LLM 引擎        : 未配置（只走术语表，其余直接跳过）")

    guard, by_glossary, need_llm = [], {}, []
    for k in todo:
        if is_untranslatable(k, never):
            guard.append(k)
            continue
        nk = norm(k)
        if nk in exact:
            by_glossary[k] = exact[nk]
            continue
        sk = skeleton(k)
        if has_placeholder(k) and sk in skel:
            # 骨架相同但原文不同：占位符的个数与种类都必须一致才敢沿用，
            # 否则会把 "%@" 的译文套到 "%1$@" 上（虽然多数情况等价，但不该赌）。
            src, val = skel[sk]
            if sorted(PLACEHOLDER.findall(k)) == sorted(PLACEHOLDER.findall(src)):
                by_glossary[k] = val
                continue
        need_llm.append(k)

    print(f"不译（常量/数值）: {len(guard)}")
    print(f"术语表命中      : {len(by_glossary)}")
    print(f"待 LLM 兜底     : {len(need_llm)}")

    # ---------------- LLM ----------------
    llm_out, rejected, failed = {}, [], []
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()

    if need_llm and (api_key or args.llm):
        if not api_key:
            print("⚠️  未设置 LLM_API_KEY，跳过 LLM 兜底"
                  "（这批文案将直接跳过，不再留待办）")
            failed = need_llm
        else:
            # 术语表提示词：只取短词条，避免把整句塞进 prompt
            hint_rows = sorted({(k, v) for k, v in load_tsv(
                os.path.join(ROOT, "translations", "glossary.tsv")).items()
                if len(k.split()) <= 4})
            hint = "\n".join(f"{k} = {v}" for k, v in hint_rows)
            for i in range(0, len(need_llm), args.batch):
                chunk = need_llm[i:i + args.batch]
                label = f"[{i + 1}-{i + len(chunk)}/{len(need_llm)}]"
                try:
                    got = llm_translate(chunk, api_key, base_url, model, hint)
                except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
                        ValueError, TimeoutError) as exc:
                    print(f"  {label} ❌ 调用失败：{exc}")
                    failed += chunk
                    continue
                clean, bad = keys_ok(chunk, got)
                llm_out.update(clean)
                rejected += bad
                missing = [k for k in chunk if k not in clean]
                failed += missing
                print(f"  {label} ✅ {len(clean)} 条，"
                      f"退回 {len(missing) + len(bad)} 条")
    else:
        failed = need_llm

    # ---------------- 落盘 ----------------
    merged = {k: v for k, v in by_glossary.items()}
    merged.update(llm_out)
    known = load_tsv(os.path.join(ROOT, "translations", "curated.tsv"))
    # 已经人工校对过的，不要用自动结果覆盖
    for k in list(merged):
        if k in known:
            merged.pop(k)
            by_glossary.pop(k, None)
            llm_out.pop(k, None)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("# 由 scripts/tools/translate_missing.py 自动生成，请勿手工编辑。\n")
        fh.write("# 人工修完请把满意的条目移进 translations/curated.tsv。\n")
        for k in sorted(merged):
            fh.write(f"{k}\t{merged[k]}\n")

    if rejected:
        print()
        print("⚠️  LLM 产出被拦下的（占位符/中文检查未过）：")
        for k, v, why in rejected[:10]:
            print(f"   [{why}] {k!r} -> {v!r}")

    # 没译上的：只报数，不留待办（见文件头「翻不了的直接跳过」）
    skipped = sorted(set(failed) | {r[0] for r in rejected})

    print()
    print(f"写入 {os.path.relpath(args.out, ROOT)} : {len(merged)} 条")
    print(f"  其中术语表命中 {len(by_glossary)}，LLM 产出 {len(llm_out)}")
    print(f"跳过（没译上）: {len(skipped)} 条 —— 不写待办、不开 Issue，直接跳过")
    for k in skipped[:15]:
        print(f"   · {k!r}")
    if len(skipped) > 15:
        print(f"   … 其余 {len(skipped) - 15} 条同类，不再列出")
    if skipped:
        print("   （原因通常是：术语表未命中且未配 LLM_API_KEY，或模型没给出合格结果。")
        print("    想自己补：把 key<TAB>译文 加进 translations/curated.tsv。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
