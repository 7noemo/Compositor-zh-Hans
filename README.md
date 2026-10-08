# Compositor 简体中文版

给 [Compositor](https://github.com/robbietilton/Compositor)（macOS 图像编辑器）做的**完整简体中文发行版**，
外加一套**自动跟随上游 Release** 的流水线。

上游作者明确不接受本地化 PR（[#57](https://github.com/robbietilton/Compositor/issues/57) /
[#74](https://github.com/robbietilton/Compositor/issues/74) /
[#123](https://github.com/robbietilton/Compositor/issues/123) /
[#205](https://github.com/robbietilton/Compositor/issues/205) /
[#222](https://github.com/robbietilton/Compositor/issues/222)），
所以这里不往上游推代码，而是把汉化做成一个独立可复现的发行版。

---

## 给使用者：怎么装

### 一键装

到 [Releases](../../releases/latest) 下载 **`一键安装汉化版.command`**，双击。

> 首次双击若提示「无法打开」：右键 → 打开 → 打开。（这是 macOS 对下载脚本的默认拦截，只需一次。）

脚本会先告诉你要做什么，等你确认，然后：下载 DMG → 把旧版本**移到废纸篓**（不是删除）→ 装到「应用程序」→ 清掉隔离属性。
装完会打印旧版本在废纸篓里的文件名，想回退直接拖回去就行。

### 手动装

下载 `Compositor-x.y.z-zh-Hans.dmg`，双击挂载，把 `Compositor` 拖进「应用程序」。
首次打开被 Gatekeeper 拦的话：右键 → 打开。

### 想退回官方原版

下载 **`一键恢复官方版.command`** 双击。
它会优先用废纸篓里你原来那份原厂副本还原（签名、公证都完好），没有才去上游重新下载。

---

## 给维护者：这套流水线怎么运转

```
上游发新 Release
      │
      │ 每 6 小时轮询一次
      ▼
┌─────────────────────────────────────────────────────────┐
│ Sync upstream translations   (.github/workflows/…)      │
│  1. 比对 state/upstream.json 记的 tag 与上游最新 tag      │
│  2. 变了 → 浅克隆那个 tag 到 _upstream/                   │
│  3. 打本地化补丁（localize_patch.py）                     │
│  4. 扫描全部界面字面量，与语言包做差集 = 「新菜单项」        │
│  5. 术语表优先命中 → 未命中的交 LLM 兜底 → 剩下进 pending  │
│  6. 合并进 Localizable.strings，跑校验，更新 state        │
│  7. 提交，并触发下面的出包流水线                           │
└─────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│ Build & release macOS app   (.github/workflows/…)       │
│  1. 自检：补丁幂等 / swiftc -parse 全量语法 / 覆盖率阈值   │
│  2. xcodebuild Release（ad-hoc 签名）                    │
│  3. 注入 zh-Hans.lproj + 改 CFBundleDevelopmentRegion    │
│  4. 重签名 + 自检 + 打 DMG                               │
│  5. 发布 Release，附上一键安装 / 一键恢复脚本              │
└─────────────────────────────────────────────────────────┘
```

### 首次建仓后要做三件事

```bash
# 1. 把仓库里所有 __REPO__ 换成你的地址（幂等，跑两次也没事）
bash scripts/set-repo.sh 你的用户名/Compositor-zh-Hans
git add -A && git commit -m '设置仓库地址' && git push

# 2. GitHub 仓库 → Settings → Actions → General
#    Workflow permissions 选 "Read and write"
#    勾上 "Allow GitHub Actions to create and approve pull requests"

# 3. （可选）想启用 LLM 兜底翻译：
#    Settings → Secrets and variables → Actions
#      Secret: LLM_API_KEY
#      Variable: LLM_BASE_URL（默认 https://api.openai.com/v1）
#      Variable: LLM_MODEL（默认 gpt-4o-mini）
#    不配也能跑：术语表命中的照补，其余留在 state/pending/ 等你人工过。
```

然后到 Actions 手动跑一次 **Sync upstream translations**。
它会把上游语言包对齐一遍；有改动就提交，并自动接力触发 **Build release** 出包。

> **忘了跑第 1 步也不要紧。** build 流水线每次都会用本次运行的真实仓库名
> 再跑一遍 `set-repo.sh`，所以 fork 之后不改任何文件，出的包也会正确指向你自己的仓库
> （Sparkle 更新源、「检查更新」菜单、一键脚本的下载地址）。
> 但本地直接跑 `scripts/bootstrap.sh` 时它没有这个兜底，会明确报错让你补 `--repo`。

### 本地复现

```bash
bash scripts/bootstrap.sh                # 取上游源码 + 打补丁 → _upstream/
bash scripts/selfcheck.sh                # 雷区检查 / 幂等 / 语法 / 语言包 / 覆盖率
bash scripts/build.sh                    # 编译 + 打包 → dist/*.dmg（需要完整 Xcode）
```

`scripts/build.sh` 需要**完整 Xcode**。如果 `xcode-select -p` 指向的是
Command Line Tools，它会在第一步就明确报错退出（只有 `swiftc -parse` 是不够编译的）。
自检那步不需要 Xcode，可以随时单独跑。

网络受限时（clone 走不通），可以拿一份本地上游源码副本离线打补丁：

```bash
bash scripts/bootstrap.sh --from-local /path/to/upstream-src \
     --src /tmp/up --repo 你的用户名/Compositor-zh-Hans v1.4.6
bash scripts/selfcheck.sh --src /path/to/upstream-src
```

---

## 目录说明

| 路径 | 作用 |
| --- | --- |
| `zh-Hans.lproj/Localizable.strings` | **本仓库的主要作品**：全部简体中文词条 |
| `translations/curated.tsv` | 人工校对的译文（优先级最高，自动结果不会覆盖它） |
| `translations/glossary.tsv` | 术语表。改这里就能影响下一版所有新词条的用词 |
| `translations/auto.tsv` | 自动补齐的译文（术语表 + LLM 的产出，可随时删掉重来） |
| `translations/never-translate.txt` | 永不翻译清单（PSD 常量、单位、商品名…） |
| `state/upstream.json` | 已同步到的上游版本、覆盖率、历史记录 |
| `state/pending/untranslated.tsv` | 术语表和 LLM 都没搞定的词条，等你处理 |
| `scripts/tools/localize_patch.py` | **核心**：把上游源码改造成可完整汉化的版本 |
| `scripts/tools/extract_strings.py` | 扫出所有界面文案，与语言包做差集 |
| `scripts/tools/translate_missing.py` | 术语表优先 + LLM 兜底补译文 |
| `scripts/tools/merge_translations.py` | 把译文合并进语言包（含去重、占位符检查） |
| `scripts/tools/check-strings.py` | 语言包校验（语法、重复 key、占位符一致性） |
| `scripts/bootstrap.sh` | 取源码 + 打补丁 |
| `scripts/build.sh` | 编译 + 注入语言包 + 签名 + DMG |
| `scripts/selfcheck.sh` | 出包前的自检 |
| `scripts/install.sh` / `restore.sh` | 一键装 / 一键还原 |

---

## 为什么需要「本地化补丁」：问题到底出在哪

上游界面文案全都有，但分两类：

**A 类 —— 字面量直接出现在本地化位置**

```swift
Text("Add layer effect")            // SwiftUI 拿它当 LocalizedStringKey 查表
.help("Increase the brush size")
```

这类只要往 `.app` 里放一个 `zh-Hans.lproj/Localizable.strings` 就能汉化。

**B 类 —— 字面量先赋给 String，再进视图**

```swift
let title = "Adjustment"                        // 先存成 String
Circle().fill(gradient)                          // …

Text(title)                                      // ← String 重载：原样渲染，不查表
.help("Fade the selection by \(pixels) pixels")  // ← 插值：运行时已格式化，查不到
```

`Text(_ content: String)`、`.help(_ text: String)` 这类**接收 String 的重载不会查表**。
字符串插值 `"Nudge \(direction) 1 px"` 更麻烦：它在运行时就已经拼好了，
就算真去查表也匹配不上 `"Nudge %@ 1 px"` 这样的 key。

**这就是「大部分界面已经中文了，但小工具组件和弹窗提示还是英文」的根因。**

补丁做三件事解决它：

1. 注入运行时查表助手（`Compositor/Localized.swift`）：

   ```swift
   func L(_ key: String) -> String {
       guard !key.isEmpty else { return key }
       return Bundle.main.localizedString(forKey: key, value: key, table: nil)
   }
   ```

   `value: key` 是关键 —— **查不到就原样返回**。最坏结果是「没翻译」，绝不会显示错内容或崩溃，
   所以对用户数据（图层名、文件名）也是安全的。

2. 把 B 类的渲染点包一层：`Text(title)` → `Text(L(title))`。

3. 把插值消息改写成显式格式串：`"Nudge \(d) 1 px"` → `LF("Nudge %@ 1 px", d)`。

### 包裹实参时踩过的坑

第一版用一条正则匹配 `Text(...)` 的实参，结果在这行上翻车：

```swift
.help("Add layer effect").accessibilityLabel("Layer effects")
```

字符类 `[^()]` 无法表达「括号要配平」，正则把第一个 `)` 一起吃掉了，
一次匹配跨到了第二个修饰符上，产出 `.help(L("Add layer effect").accessibilityLabel("Layer effects"))` —— 括号少一个，代码编不过。

现在改成**括号配平 + 字符串字面量感知的逐实参扫描**（`wrap_line()` / `_find_close()`）；
跨行、含 `\(` 插值、含嵌套调用的实参一律放过。

**这类问题只有真去编译（或至少 `swiftc -parse`）才会暴露**，
所以 `scripts/selfcheck.sh` 把「补丁后 146 个 Swift 文件全部 `swiftc -parse` 通过」
设成了硬门槛，而不是靠肉眼看 diff。

### 写脚本时踩过的坑（中文项目特有的）

**`$VAR` 后面跟着中文，必须写成 `${VAR}`。**

macOS 自带的是 bash **3.2**，在 UTF-8 locale 下会把紧跟在变量名后面的多字节字符
吞进变量名：

```bash
# 在 macOS 上会报 "TARGET（: unbound variable" 并终止脚本
say "✅ 安装完成：$TARGET（版本 $NEW_VER）"
# 正确写法
say "✅ 安装完成：${TARGET}（版本 ${NEW_VER}）"
```

要命的地方在于：**Linux 的 bash 5 完全不会这样**，所以 CI 全绿，
只有用户在自己机器上双击一键脚本时才炸。这类问题在 `install.sh` / `restore.sh`
里一共 18 处，都已修掉。

为了不让它回来，加了 `scripts/tools/lint-shell.py`，并把结果接进
`scripts/selfcheck.sh`（也就是 CI 的 build 流水线），命中即失败。

同一个 lint 还顺带告警另一类坑：`set -euo pipefail` 下
`VAR="$(可能失败的命令 | 另一个命令)"` 会让整个赋值语句失败、脚本静默终止。
典型受害者是 `codesign -dv`（未签名包返回非 0）、`curl`（断网）、
`grep`（无匹配返回 1）。修法是末尾补 `|| true`，或把值包进 `if`，
让后面的判空和友好报错有机会执行。

---

## 已知限制

* **命令面板（⇧⌘P）的搜索仍按英文匹配。** 显示是中文，但要搜到某个工具得输入英文
  （`entry.title` 同时充当显示文本和检索文本，改成中文会让英文搜不到）。
* **未做 Apple 公证。** 用 ad-hoc 签名，首次打开可能需要「右键 → 打开」；一键脚本会自动处理。
* **约 80 条未翻译**，基本是 `8BIM` / `TySh` 这类 PSD 二进制标记、纯数字读数、
  商品名（MacBook、iPhone）与 Swift 字符串插值的切分碎片。这些翻了反而会出错。
* **上游若大改视图层**，补丁的锚点可能失配。这时 CI 会报「插值规则未命中」或
  「带 L() 的渲染点少于 300 个」而失败 —— 这是有意设计的报警，不是静默降级。

---

## 许可与声明

上游 Compositor 为 MIT 许可，版权归 Wonder Assembly LLC。本仓库对上游代码的改动、
以及新增的语言包与脚本，同样以 MIT 发布。详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。

本项目与 Wonder Assembly LLC **无任何隶属或合作关系**。
