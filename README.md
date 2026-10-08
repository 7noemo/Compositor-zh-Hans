# Compositor 简体中文版

> **把 macOS 图像编辑器 [Compositor](https://github.com/robbietilton/Compositor) 完整汉化的非官方简体中文发行版。**
> 不用自己装 Xcode、不用懂代码，下载双击就能用；上游发新版时这个仓库会自动跟上。

| | |
| --- | --- |
| 当前跟随上游 | **v1.4.6**（2026-10-08 发布） |
| 界面文案覆盖率 | **92.9%**（已翻译 1070 / 共扫出 1152 条） |
| 语言包词条总数 | 1312 条 |
| 运行要求 | **macOS 26.0 或更高** + **Apple 芯片**（M 系列） |
| 签名方式 | ad-hoc（未做 Apple 公证，首次打开需放行一次） |

**如果你是来找中文版 Compositor 的，直接跳到 [下载](#下载) → [安装](#安装) 就行。**

---

## 目录

- [一、这是什么](#一这是什么)
- [二、运行环境](#二运行环境)
- [三、下载](#下载)
- [四、安装](#安装)
- [五、升级到新版](#升级到新版)
- [六、恢复到官方原版 / 卸载](#恢复到官方原版--卸载)
- [七、汉化到什么程度](#汉化到什么程度)
- [八、常见问题](#常见问题)
- [九、反馈问题](#反馈问题)
- [十、给想自己构建的人](#给想自己构建的人)
- [许可与声明](#许可与声明)

---

## 一、这是什么

[Compositor](https://github.com/robbietilton/Compositor) 是一款免费开源的 macOS 图像编辑器，
作者是 Wonder Assembly LLC。它的定位是「Photoshop 的平替」：图层、蒙版、调整图层、
图层效果、Camera Raw 滤镜、选区、绘画与修饰、PSD 导入、命令面板（⌘F）……该有的都有，
而且完全免费、源码开放。

**但它只有英文界面。** 上游作者明确表示不接受本地化相关 PR
（[#57](https://github.com/robbietilton/Compositor/issues/57) /
[#74](https://github.com/robbietilton/Compositor/issues/74) /
[#123](https://github.com/robbietilton/Compositor/issues/123) /
[#205](https://github.com/robbietilton/Compositor/issues/205) /
[#222](https://github.com/robbietilton/Compositor/issues/222)），
社区提交的十几个汉化 PR 也都没被合并。

所以这个仓库走的是另一条路：**不往上游推代码，而是把汉化做成一个独立、可复现的发行版。**

具体做法是：拉取上游源码 → 自动打一层本地化补丁 → 用 Xcode 编译 → 注入中文语言包 →
ad-hoc 签名 → 打包成 DMG 发布。整个过程由 GitHub Actions 自动完成。

### 你能得到什么

* **开箱即用的中文界面**：下载 `一键安装汉化版.command` 双击，或手动装 DMG。
* **不是「大部分中文」**：连小工具组件、滑杆提示、弹窗按钮、撤销栈里的操作名
  （「添加图层」「对齐图层」…）这些上游最容易被漏掉的地方都翻了。覆盖率 92.9%。
* **能一键退回官方原版**：安装时会把你原来那份原厂副本放进废纸篓，
  随时可以一键还原，签名和公证都是完好的。
* **持续跟进上游更新**：本仓库每 6 小时检查一次上游 Release，
  发现新版会自动重新扫描新出现的界面文案、补译、重新编译发包。

### 这不是什么

* **不是官方版本**，与 Wonder Assembly LLC **没有任何隶属或合作关系**。
* **不会上传你的任何数据**。汉化只改界面文案，图片处理逻辑一行没动。
* **不吃掉你的工程文件**。`.comp` 工程、PSD、导出格式全部与官方版一致、可互操作。

---

## 二、运行环境

| 要求 | 说明 |
| --- | --- |
| **macOS 26.0 或更高** | 上游工程把 `MACOSX_DEPLOYMENT_TARGET` 设为 `26.0`，比这更低的系统**无法运行**，也装不上 |
| **Apple 芯片**（M1/M2/M3/M4…） | 上游只支持 Apple silicon，不支持 Intel Mac |
| 磁盘空间 | 约 200 MB |
| 网络 | 只有「一键安装」脚本需要联网下载；用 DMG 手动装则完全离线 |

> **为什么系统要求这么高？** 这是上游自己的选择 —— 它用了 macOS 26 才有的 API。
> 这不是汉化引入的限制，装官方原版同样要求 macOS 26。

---

## 下载

打开 **[最新 Release](../../releases/latest)**，里面有三个文件：

| 文件名 | 说明 |
| --- | --- |
| `Compositor-<版本>-zh-Hans.dmg` | 汉化版安装包。想手动装、或想先留个备份就用它 |
| `一键安装汉化版.command` | **推荐**。双击后自动下载最新汉化版并装好，还会处理 Gatekeeper 拦截 |
| `一键恢复官方版.command` | 想退回官方原版时双击它 |

---

## 安装

### 方式 A：一键安装（推荐）

1. 在 Release 页面下载 **`一键安装汉化版.command`**。
2. **双击它**。
3. 如果 macOS 提示「无法打开，因为它来自身份不明的开发者」：
   **右键点这个文件 → 选「打开」→ 再点「打开」**。（只有第一次需要这样做。）
4. 终端窗口会打开，先列清楚它打算做什么，等你看完按回车确认。
5. 装完窗口会停住并显示结果，按任意键关闭。

它做的事，按顺序是：

1. 检查你的电脑是不是 macOS 26 + Apple 芯片；
2. 从本仓库 Release 下载最新的汉化版 DMG；
3. 如果你「应用程序」里**已经有 Compositor**，把它**移到废纸篓**（注意：是移到废纸篓，不是删除）；
4. 把汉化版装进 `/Applications`；
5. 清掉 `com.apple.quarantine` 隔离属性（这样打开时不会弹「已损坏」）；
6. 自检：确认语言包在包里、版本号正确；
7. 告诉你旧版本在废纸篓里的**完整文件名**，随时可以拖回去。

> 如果你不想让它问你，可以加 `--yes`：
> `bash scripts/install.sh --yes`（跳过确认，其余行为一样）

### 方式 B：手动安装 DMG

1. 下载 `Compositor-<版本>-zh-Hans.dmg`；
2. 双击挂载；
3. 把里面的 **Compositor** 拖进「应用程序」（DMG 里已经放好了「应用程序」快捷方式）；
4. 首次打开被拦的话，见下一节。

### 首次打开被 macOS 拦住

因为这个包**没有 Apple 公证**（公证需要每年 99 美元的开发者账号），
macOS 会拦一下。有两种放行方式：

**方法一（最简单）**

1. 在「应用程序」里找到 Compositor；
2. **右键**（或按住 Control 点）→ 选「**打开**」；
3. 弹窗里再点一次「**打开**」。

**方法二（如果方法一没出现「打开」按钮）**

1. 先双击一次 Compositor（会失败，没关系）；
2. 打开 **系统设置 → 隐私与安全性**；
3. 往下拉，会看到「已阻止使用 Compositor……」，点旁边的「**仍要打开**」；
4. 再双击一次就可以了。

> 用「一键安装」脚本的话，第 5 步会直接清掉隔离属性，通常**根本不会遇到这个问题**。

### 它会覆盖我原来的 Compositor 吗？

不会丢东西，但会替换文件位置：

* 旧的那份会被**移动**到 `~/.Trash`，文件名形如 `Compositor-备份-20261008-153000.app`；
* 你的工程文件、偏好设置都在别的地方，完全不受影响；
* 想换回来：打开废纸篓，把那个 `.app` 拖回「应用程序」即可。

---

## 升级到新版

**上游发新版之后，这个仓库会自动编译出对应的中文版。**
你不需要做任何事，只要在 [Releases](../../releases/latest) 看到新版本时，
再跑一次「一键安装汉化版」就行 —— 它会自动把旧版送进废纸篓、装上新版。

### 为什么汉化版关掉了「自动更新」

上游的 Compositor 自带 Sparkle 自动更新。汉化版**必须把它关掉**，否则：

> 下次它自动更新，会下载回一份**没有中文语言包的官方版本**，你的界面就变回英文了。

所以汉化版做了三件事：

1. `SUEnableAutomaticChecks` / `SUAutomaticallyUpdate` 都设为 `false`（不再后台自动更新）；
2. 菜单里的「检查更新…」改成**打开本仓库的 Releases 页面** —— 也就是中文版的更新入口；
3. 更新源指向本仓库。

一句话：**汉化版的更新走本仓库，不走上游。**

---

## 恢复到官方原版 / 卸载

### 一键还原

下载 Release 里的 **`一键恢复官方版.command`**，双击。它会：

1. **优先**从废纸篓里找你原来那份原厂副本，直接还原回去（签名、公证都是完好的）；
2. 废纸篓里没有（比如你清空过），就自动从上游 GitHub Release 重新下载官方 DMG 装上；
3. 最后自检，确认包里的中文语言包**已经不在了**。

也可以指定想还原到哪个上游版本：

```bash
bash scripts/restore.sh --tag v1.4.6
```

### 彻底卸载

1. 把「应用程序」里的 `Compositor.app` 拖进废纸篓；
2. （可选）删掉偏好设置：
   ```bash
   rm -rf ~/Library/Preferences/com.wonderassembly.compositor.plist
   rm -rf ~/Library/Saved\ Application\ State/com.wonderassembly.compositor.savedState
   ```
3. 别忘了一起清掉废纸篓里的备份，否则它一直占着几百 MB。

---

## 汉化到什么程度

**覆盖率 92.9%** —— 从源码里扫出 1152 条人可读的界面文案，已经翻了 1070 条。

### 已经汉化的

* 全部菜单、菜单项、快捷键说明；
* 所有面板标题、字段标签、按钮、单选/分段控件；
* 工具组件（笔刷、套索、渐变、形状、变换…）的标题与滑杆提示；
* 弹窗与对话框的正文、按钮、错误提示；
* **命令面板（⌘F）**里的全部工具名；
* **撤销/重做栈里的操作名**（「添加图层」「对齐图层」「翻转画布」…）；
* 数值读数的单位与说明文字（像素 / 百分比 / 英寸）。

### 没有汉化的，以及为什么

剩余 82 条**故意不翻**，翻了反而会出问题：

| 类别 | 例子 | 为什么不动 |
| --- | --- | --- |
| PSD 二进制里的标记 | `8BIM`、`TySh` | 这是文件格式的内部标识，改了会读不出 PSD |
| 纯数字/数值读数 | `1024 × 768`、`100%` | 本来就不需要翻译 |
| 设备与商品名 | `MacBook`、`iPhone`、`Studio Display` | 品牌名不译 |
| 字符串插值的切分碎片 | `R `、` —   G —   B —`、`Tool › ` | 是拼装格式串时的中间产物，单独翻译会错位 |

### 一个已知限制

**命令面板（⌘F）的搜索仍然按英文匹配。** 显示是中文，但要搜到某个工具，
得输入它的英文名（例如输入 `brush` 能找到「画笔」）。
原因是每个条目只有一份文本，既当显示名又当检索关键字；改成中文会让英文搜不到，
反而更难用。这是刻意的取舍。

---

## 常见问题

<details>
<summary><b>双击后提示「无法打开，因为它来自身份不明的开发者」</b></summary>

这是 macOS 对**未公证**应用的默认拦截。右键点文件 → 选「打开」→ 再点「打开」。
只有第一次需要这样做，之后就正常了。

</details>

<details>
<summary><b>提示「Compositor 已损坏，无法打开」</b></summary>

这不是真的损坏，是隔离属性（quarantine）在起作用。清掉它：

```bash
xattr -cr /Applications/Compositor.app
```

或者干脆用「一键安装汉化版.command」重装一次，脚本会自动清。

</details>

<details>
<summary><b>装完了，但界面还是英文</b></summary>

先确认你打开的是**新装进去的那份**：

```bash
ls /Applications/Compositor.app/Contents/Resources/ | grep zh-Hans
```

应该能看到 `zh-Hans.lproj`。如果没有，说明装的是官方版（比如系统里有两份），
用「一键安装汉化版」重装一次。

另外注意：汉化版已经把 `CFBundleDevelopmentRegion` 设成 `zh-Hans`、并且只声明这一种语言，
所以**不管你的系统语言是什么，都会显示中文**，不需要去改系统语言。

</details>

<details>
<summary><b>macOS 版本不够 / 我是 Intel Mac</b></summary>

上游 Compositor 要求 **macOS 26.0+ 且 Apple 芯片**，汉化版继承同样要求
（我们只改文案，不动代码和最低系统版本）。装不了的话只能升级系统或换机器。

</details>

<details>
<summary><b>它是免费的吗？会不会有广告/收费？</b></summary>

上游是 MIT 许可的免费开源软件，汉化版同样是 MIT，**完全免费、无广告、无内购**。
这个仓库不接收任何形式的付费。

</details>

<details>
<summary><b>汉化会不会影响图片处理结果？</b></summary>

不会。补丁**只动界面文案的取用方式**，图像处理、PSD 解析、导出编码的代码一行没改。
另外即便补丁出现了意外，它的失败模式也只是「这句没翻译」——
因为我们用的查表函数在查不到时会**原样返回**，绝不会显示错内容，更不会崩溃。

</details>

<details>
<summary><b>我的图层名 / 文件名会被翻译吗？</b></summary>

不会。补丁对用户内容（图层名 `item.layerName`、工程名 `tab.title`）
做了**白名单排除**，明确不查表。
所以你把图层命名为 "Save" 不会突然变成「存储」。

</details>

<details>
<summary><b>汉化的质量是怎么保证的？</b></summary>

三道关：

1. **术语表优先**：`translations/glossary.tsv` 里是按 **Photoshop 中文版**的用词
   定的术语（图层 / 选区 / 绘画 / 调整 / 变换 / 文字 / 界面分组），命中即用，保证前后一致；
2. **人工校对本优先**：`translations/curated.tsv` 是逐条看过的译文，自动结果永远不会覆盖它；
3. **自动校验**：每次合并都会检查 `.strings` 语法、重复 key、**占位符是否与原文一致**
   （`%@` 的数量和种类必须对得上，否则会漏掉变量甚至崩溃）。

新词条如果术语表和 LLM 都拿不准，会被丢进 `state/pending/untranslated.tsv` 等人处理，
**不会硬塞一个瞎猜的翻译进去**。

</details>

<details>
<summary><b>我可以自己改译文吗？</b></summary>

可以，而且很欢迎。最短路径：

1. Fork 本仓库；
2. 直接编辑 `zh-Hans.lproj/Localizable.strings`，或把译文加进 `translations/curated.tsv`；
3. 提 PR。

`curated.tsv` 是「人工校对」通道，优先级最高，下次自动同步时不会被覆盖。

</details>

---

## 反馈问题

* **汉化不对 / 有漏译 / 术语不统一** → 在本仓库提 [Issue](../../issues/)，
  附上**截图**和你是在哪个位置看到的，最好再说明期望的中文用词。
* **App 本身的功能 bug**（图片处理出错、导出异常、崩溃）→ 请提到
  [上游仓库](https://github.com/robbietilton/Compositor/issues)，
  并且**说明你用的是官方版还是汉化版**。汉化只改文案，功能问题都在上游。
* **安装脚本报错** → 把终端里的完整输出贴上来，那里面已经带了定位信息。

---

## 给想自己构建的人

不需要自己构建就能用（见上文）。以下内容只在你**想改译文、想自己出包**时才有用。

### 目录说明

| 路径 | 作用 |
| --- | --- |
| `zh-Hans.lproj/Localizable.strings` | **本仓库的主要作品**：全部简体中文词条（1312 条） |
| `translations/curated.tsv` | 人工校对的译文（优先级最高，自动结果不会覆盖它） |
| `translations/glossary.tsv` | 术语表。改这里就能影响下一版所有新词条的用词 |
| `translations/auto.tsv` | 自动补齐的译文（术语表 + LLM 的产出，可随时删掉重来） |
| `translations/never-translate.txt` | 永不翻译清单（PSD 常量、单位、商品名…） |
| `state/upstream.json` | 已同步到的上游版本、覆盖率、历史记录 |
| `state/pending/untranslated.tsv` | 术语表和 LLM 都没搞定的词条，等人处理 |
| `scripts/tools/localize_patch.py` | **核心**：把上游源码改造成可完整汉化的版本 |
| `scripts/tools/extract_strings.py` | 扫出所有界面文案，与语言包做差集 |
| `scripts/tools/translate_missing.py` | 术语表优先 + LLM 兜底补译文 |
| `scripts/tools/merge_translations.py` | 把译文合并进语言包（含去重、占位符检查） |
| `scripts/tools/check-strings.py` | 语言包校验（语法、重复 key、占位符一致性） |
| `scripts/tools/lint-shell.py` | shell 脚本雷区检查（见下文「踩过的坑」） |
| `scripts/tools/lint-swift.py` | L() 调用形状检查（见下文「踩过的坑」） |
| `scripts/bootstrap.sh` | 取上游源码 + 打补丁 |
| `scripts/build.sh` | 编译 + 注入语言包 + 签名 + 打 DMG |
| `scripts/selfcheck.sh` | 出包前的全套自检 |
| `scripts/install.sh` / `restore.sh` | 一键装 / 一键还原 |
| `scripts/set-repo.sh` | 把仓库里所有 `__REPO__` 占位符换成你的地址 |

### 自动化流水线

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
│  7. 提交                                                  │
└─────────────────────────────────────────────────────────┘
      │
      │ workflow_run（同步成功才接力）
      ▼
┌─────────────────────────────────────────────────────────┐
│ Build & release macOS app   (.github/workflows/…)       │
│  1. 自检：雷区 / L() 形状 / 幂等 / swiftc -parse / 覆盖率  │
│  2. xcodebuild Release（ad-hoc 签名，日志落盘）           │
│  3. 注入 zh-Hans.lproj + 改 CFBundleDevelopmentRegion    │
│  4. 重签名 + 自检 + 打 DMG                               │
│  5. 发布 Release，附上一键安装 / 一键恢复脚本              │
└─────────────────────────────────────────────────────────┘
```

判定「上游有没有新增菜单项」的做法**不是比对菜单**，而是把新版本源码里所有
「人可读的字面量」全量抽出来跟现有语言包做差集。这样无论上游是加了菜单项、
改了提示文案，还是把原本硬编码的字符串搬进了新组件，都跑不掉。

### 首次建仓后要做三件事

```bash
# 1. 把仓库里所有 __REPO__ 换成你的地址（幂等，跑两次也没事）
bash scripts/set-repo.sh 你的用户名/Compositor-zh-Hans
git add -A && git commit -m '设置仓库地址' && git push

# 2. GitHub 仓库 → Settings → Actions → General
#    Workflow permissions 选 "Read and write"
#    勾上 "Allow GitHub Actions to create and approve pull requests"
#    （不设的话 CI 无法提交语言包、也无法建 Release）

# 3. （可选）想启用 LLM 兜底翻译：
#    Settings → Secrets and variables → Actions
#      Secret: LLM_API_KEY
#      Variable: LLM_BASE_URL（默认 https://api.openai.com/v1）
#      Variable: LLM_MODEL（默认 gpt-4o-mini）
#    不配也能跑：术语表命中的照补，其余留在 state/pending/ 等人工过。
```

然后到 Actions 手动跑一次 **Build & release macOS app**（输入留空），
就能拿到第一个 `v1.4.6-zh` Release。

> **忘了跑第 1 步也不要紧。** build 流水线每次都会用本次运行的真实仓库名
> 再跑一遍 `set-repo.sh`，所以 fork 之后不改任何文件，出的包也会正确指向你自己的仓库
> （Sparkle 更新源、「检查更新」菜单、一键脚本的下载地址）。
> 但本地直接跑 `scripts/bootstrap.sh` 时没有这个兜底，它会明确报错让你补 `--repo`。

### 本地复现

```bash
bash scripts/bootstrap.sh                # 取上游源码 + 打补丁 → _upstream/
bash scripts/selfcheck.sh                # 雷区 / L() 形状 / 幂等 / 语法 / 语言包 / 覆盖率
bash scripts/build.sh                    # 编译 + 打包 → dist/*.dmg（需要完整 Xcode）
```

`scripts/build.sh` 需要**完整 Xcode 26**。如果 `xcode-select -p` 指向的是
Command Line Tools，它会在第一步就明确报错退出（只有 `swiftc -parse` 是不够编译的）。
自检那步不需要 Xcode，可以随时单独跑。

网络受限时（`git clone` 走不通），可以拿一份本地上游源码副本离线打补丁：

```bash
bash scripts/bootstrap.sh --from-local /path/to/upstream-src \
     --src /tmp/up --repo 你的用户名/Compositor-zh-Hans v1.4.6
bash scripts/selfcheck.sh --src /path/to/upstream-src
```

### 为什么需要「本地化补丁」：问题到底出在哪

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

### 踩过的坑（每个都真实炸过一次）

<details>
<summary><b>坑 1：正则表达不了括号配平</b></summary>

第一版用一条正则匹配 `Text(...)` 的实参，结果在这行上翻车：

```swift
.help("Add layer effect").accessibilityLabel("Layer effects")
```

字符类 `[^()]` 无法表达「括号要配平」，正则把第一个 `)` 一起吃掉了，
一次匹配跨到了第二个修饰符上，产出
`.help(L("Add layer effect").accessibilityLabel("Layer effects"))` —— 括号少一个，代码编不过。

现在改成**括号配平 + 字符串字面量感知的逐实参扫描**（`wrap_line()` / `_find_close()`）；
跨行、含 `\(` 插值、含嵌套调用的实参一律放过。

</details>

<details>
<summary><b>坑 2：多参数调用被整体包进 L()</b></summary>

```swift
Label("New", systemImage: "plus")
→ Label(L("New", systemImage: "plus"))     # 语法合法，编译期报 extra argument
```

`L()` 只收一个参数，把**整个实参列表**塞进去必然编译失败。
但 `swiftc -parse` 只做语法分析，这类错误它**完全看不出来** ——
于是「本地自检全绿、CI 的 xcodebuild 以 65 退出」，只能靠反复重跑 15 分钟的
macOS runner 试错。

修法：多参数调用**只包第一个实参** → `Label(L("New"), systemImage: "plus")`。
（对 `Label` 而言，第一个参数从 `LocalizedStringKey` 换成 `String` 会走
`init<S: StringProtocol>(_ title: S, systemImage:)` 重载，而它本来就不查表 ——
正好是我们想要的，查表已经由 `L()` 做完了。）

为防止再犯，新增 `scripts/tools/lint-swift.py` 并接进自检，
专门检查 L() 的调用形状（多实参 / 参数标签）。

</details>

<details>
<summary><b>坑 3：补丁包了「非 String」的表达式</b></summary>

补丁是**文本级**改写，个别位置可能把 Int 型枚举裸值、可选值、自定义类型也包进来，
编译不过就整个包都出不来。

修法：给 `L()` 加一个兜底重载，把失败模式统一成「不翻译」而不是「编译失败」：

```swift
func L(_ value: Any) -> String {
    if let text = value as? String { return L(text) }
    return String(describing: value)
}
```

Swift 的重载决议优先选更具体的类型，所以 `L("字面量")` 仍然命中那个精确重载，行为不变。

</details>

<details>
<summary><b>坑 4：<code>$VAR</code> 后面跟着中文（macOS 专属）</b></summary>

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

为了不让它回来，加了 `scripts/tools/lint-shell.py`，并接进 `selfcheck.sh`，命中即失败。

</details>

<details>
<summary><b>坑 5：<code>set -euo pipefail</code> + 命令替换失败 = 脚本静默死掉</b></summary>

`VAR="$(可能失败的命令 | 另一个命令)"` 的退出码就是整条赋值语句的退出码，
`set -e` 会直接终止脚本，后面那句友好的报错永远轮不到执行。

典型受害者：`codesign -dv`（未签名包返回非 0）、`curl`（断网）、
`grep`（无匹配返回 1）、`find | while read`（目录不存在）。

修法：末尾补 `|| true`，或把值包进 `if`，让判空和友好报错有机会执行。

</details>

<details>
<summary><b>坑 6：占位符哨兵被 <code>sed</code> 自己替换掉</b></summary>

`set-repo.sh` 是拿 `sed` 全局替换 `__REPO__` 的。如果某个脚本里有一行
「判断 REPO 是不是还等于占位符」，而它老老实实写成了连着的字面量，
那么 `sed` 会把**这一行**也替换掉：

```bash
if [ "$REPO" = "你的用户名/Compositor-zh-Hans" ]; then   # 原本是 "__REPO__"
  REPO=""                    # ← 于是 --repo 传进来的正常值也被清空
fi
```

症状很阴：**本地手动跑一切正常**（没跑过 `set-repo.sh`，字面量还是占位符），
但 CI 上一定失败，报「请用 --repo」，而命令里明明带着 `--repo`。

修法是把哨兵拆成两段字符串拼接（`__RE""PO__`，中间插一对空引号），`sed` 就匹配不到了。
`set-repo.sh` 替换完会立刻自查这两处哨兵是否完好，坏了**直接退出 1**。

</details>

### 已知限制（技术视角）

* **约 82 条未翻译**，理由见 [汉化到什么程度](#汉化到什么程度)。
* **命令面板搜索仍按英文匹配**，理由同上。
* **未做 Apple 公证**，首次打开可能要「右键 → 打开」。
* **上游若大改视图层**，补丁的锚点可能失配。这时 CI 会报「插值规则未命中」或
  「带 L() 的渲染点少于 300 个」而失败 —— 这是有意设计的报警，不是静默降级。

---

## 许可与声明

上游 Compositor 为 MIT 许可，版权归 Wonder Assembly LLC。本仓库对上游代码的改动、
以及新增的语言包与脚本，同样以 MIT 发布。详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。

**本项目与 Wonder Assembly LLC 无任何隶属或合作关系**，是非官方的社区汉化发行版。

Compositor 这个名字、以及原始程序的著作权属于 Wonder Assembly LLC；
本仓库只提供界面翻译与自动构建流程。
