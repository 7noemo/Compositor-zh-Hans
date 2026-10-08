# Compositor 简体中文语言包

**给 [Compositor](https://github.com/robbietilton/Compositor)（macOS 图像编辑器）用的外挂简体中文语言包。**
双击一个脚本就能把界面变成中文，双击另一个就能完全还原。不编译、不打包、不修改任何可执行代码。

[![语言包词条](https://img.shields.io/badge/语言包-1253_条-blue)](#能翻译到什么程度)
[![可翻译文案覆盖](https://img.shields.io/badge/可翻译文案覆盖-99.5%25-brightgreen)](#能翻译到什么程度)
[![上游](https://img.shields.io/badge/上游-v1.4.6-lightgrey)](https://github.com/robbietilton/Compositor/releases)
[![许可证](https://img.shields.io/badge/许可证-MIT-green)](LICENSE)

---

## 目录

- [这是什么](#这是什么)
- [这不是什么](#这不是什么)
- [运行环境](#运行环境)
- [快速开始](#快速开始)
  - [安装](#安装)
  - [还原官方版](#还原官方版)
  - [手动安装（不想跑脚本）](#手动安装不想跑脚本)
- [怎么更新](#怎么更新)
- [能翻译到什么程度](#能翻译到什么程度)
  - [实测数据](#实测数据)
  - [为什么有些地方还是英文](#为什么有些地方还是英文)
  - [其他已知限制](#其他已知限制)
- [常见问题](#常见问题)
- [反馈与贡献](#反馈与贡献)
- [给维护者](#给维护者)
- [许可与声明](#许可与声明)

---

## 这是什么

一份 `zh-Hans.lproj/Localizable.strings` —— 简体中文的界面文案对照表，
外加两个双击就能用的 shell 脚本。

Compositor 是 SwiftUI 写的，界面上的每一句文案在渲染时都会去查这张表。
官方版本里没有中文表，所以只能显示英文。本项目做的就是**把这张表放进去**，
然后让 app 重新签名一次（改了内容不重签，macOS 会拒绝启动）。

整个过程**不碰 app 的可执行文件**，图像处理、色彩管理、PSD 读写这些逻辑一行都不动。

安装脚本会顺手做三件贴心的事：

1. **先备份**一份完整的官方原版到 `~/Library/Application Support/Compositor-zh-Hans/backup/`，
   还原时直接拷回来，连 Apple 的原厂签名和公证票据都会恢复；
2. **关掉 Sparkle 自动更新** —— 这是必须的，否则官方新版会在后台被拉下来，把中文界面覆盖回英文；
3. **清掉隔离属性并重签名**，省得你每次都要去「系统设置 → 隐私与安全性」里放行。

---

## 这不是什么

- **不是二次编译的发行版**。仓库里没有上游源码副本，也不产出 DMG / zip 安装包。
  安装时只往 app 里放一份文本文件。
- **不是官方项目**。上游作者 [明确表示不接受本地化 PR](#与上游的关系)，所以本项目以「外挂」形式独立存在。
- **不是万能的**。有一类文案靠外挂翻不了，原因见[为什么有些地方还是英文](#为什么有些地方还是英文)，
  这不是漏翻，是方案的能力边界。

---

## 运行环境

| 项 | 要求 |
| --- | --- |
| 系统 | **macOS 26.0 或更新**（上游 `LSMinimumSystemVersion = 26.0`） |
| 处理器 | **Apple 芯片**（上游只发布了 arm64 版本，Intel Mac 装不了） |
| 磁盘 | 语言包本身约 80 KB；备份会额外占用约 11 MB |
| 权限 | 首次运行需要在「系统设置 → 隐私与安全性 → App 管理」里给终端放行（见 [FAQ](#常见问题)） |

---

## 快速开始

### 安装

1. 先装好**官方 Compositor**（[下载页](https://github.com/robbietilton/Compositor/releases)）。
   如果没装，安装脚本也会问你要不要顺手下载安装。
2. 到本仓库的 [Releases](../../releases/latest) 页，下载 **`install-zh-Hans.command`**。
   （它就是前面说的「一键安装语言包」，只是因为 GitHub 的限制，附件名只能用英文。）
3. **双击它**。

> ⚠️ **双击提示「你没有正确的访问权限」？**
>
> 这是浏览器下载的通病：保存文件时**不带「可执行」权限位**，跟脚本本身无关。
> 打开「终端」，把下面两行粘进去回车（就是把文件补上执行权限、去掉隔离标记）：
>
> ```bash
> chmod +x ~/Downloads/install-zh-Hans.command
> xattr -d com.apple.quarantine ~/Downloads/install-zh-Hans.command 2>/dev/null
> ```
>
> 然后**再双击**就能用了。
>
> **不想碰终端？** 下载 [`Compositor-zh-Hans-langpack-v<版本>.zip`](../../releases/latest)
> 解压后双击里面的「一键安装语言包.command」—— 压缩包里的文件保留着执行权限，
> 不会遇到这个问题（最多遇到下面那条 Gatekeeper 提示，右键放行即可）。

> **为什么附件名是英文？**
>
> GitHub 会**改写** Release 附件名里除 ASCII 以外的字符（官方文档原文：
> "GitHub renames asset filenames that have special characters, non-alphanumeric
> characters…"）。实测中文名会被换成 `default.command`，两个中文名还会撞成同一个
> 名字直接报错。所以附件只能用英文名，中文名保留在仓库文件和压缩包内部：
>
> | Release 附件（英文名） | 对应中文名 |
> | --- | --- |
> | `install-zh-Hans.command` | 一键安装语言包.command |
> | `restore-official.command` | 一键还原官方版.command |
> | `Compositor-zh-Hans-langpack-v<版本>.zip` | 语言包（内含上面两个脚本 + `说明.txt`） |
>
> 功能完全一样，双击即可运行。

> 首次双击如果提示「无法打开，因为来自身份不明的开发者」：
> 在文件上**右键 → 打开 → 再点「打开」**。只需这一次。

脚本会逐项告诉你它在做什么（找 app → 备份 → 写入语言包 → 改 Info.plist → 重签名 → 自检），
每一步都有 ✅ / ⚠️ 标记。跑完之后**退出并重新打开 Compositor**（⌘Q），界面就是中文了。

也可以克隆仓库后本地运行：

```bash
git clone https://github.com/你的用户名/Compositor-zh-Hans.git
cd Compositor-zh-Hans
bash scripts/install.sh              # 会先列清单，等你确认
bash scripts/install.sh --yes        # 不想被问就加 --yes
```

### 还原官方版

同样在 [Releases](../../releases/latest) 页下载 **`restore-official.command`**
（即「一键还原官方版.command」），双击。

它会按优先级尝试：

1. **从整包备份还原**（推荐路径）——
   把安装时留下的官方原版拷回去。原厂 Developer ID 签名和公证票据都会回来，
   等于这件事从没发生过。当前版本会先进废纸篓，随时能拖回来。
2. **就地拆除**（没有备份时的退路）——
   删掉语言包、把 `Info.plist` 的两处本地化设置改回官方值、重做一次 ad-hoc 签名。
   界面立刻回到英文，但签名签不回原厂那样（没有 Apple 的私钥）。
3. **从上游重装**（最彻底）——
   ```bash
   bash scripts/restore.sh --reinstall
   ```
   直接从上游下载官方版覆盖安装，约 10 MB。

### 手动安装（不想跑脚本）

<details>
<summary>点开看完整步骤（需要终端，5 步）</summary>

```bash
APP="/Applications/Compositor.app"

# ① 先把官方原版备份一份（很重要，退路全靠它）
ditto "$APP" ~/Compositor-官方备份.app

# ② 把语言包放进去
mkdir -p "$APP/Contents/Resources/zh-Hans.lproj"
cp zh-Hans.lproj/Localizable.strings "$APP/Contents/Resources/zh-Hans.lproj/"

# ③ 告诉系统优先挑中文
PL="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleDevelopmentRegion zh-Hans" "$PL"
/usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations array" "$PL"
/usr/libexec/PlistBuddy -c "Add :CFBundleLocalizations:0 string zh-Hans" "$PL"

# ④ 关掉 Sparkle 自动更新（否则中文会被官方新版覆盖）
/usr/libexec/PlistBuddy -c "Set :SUEnableAutomaticChecks false" "$PL"

# ⑤ 清除隔离属性 + 重新签名（改了内容就必须重签，不然打不开）
xattr -cr "$APP"
codesign --force --sign - --deep "$APP"
```

如果第 ④ 步报 `Set: Entry, ":SUEnableAutomaticChecks", Does Not Exist`，
把 `Set` 换成 `Add` 并把值写成 `bool false`。

签名这一步如果报权限错误，把命令前面加 `sudo`，
或者先在「系统设置 → 隐私与安全性 → App 管理」里给终端放行。

</details>

---

## 怎么更新

**上游发新版时，本仓库会自动跟上。** 流水线每 6 小时检查一次上游 Release：

```
上游发新 Release
      │
      ▼
 下载该 tag 的源码（不编译）
      │
      ▼
 全量扫描界面文案 → 与现有语言包做差集
      │
      ▼
 术语表优先 + LLM 兜底 补齐译文
      │
      ▼
 校验（格式 / 重复 key / 占位符一致性）
      │
      ▼
 提交语言包 → 发一个新的语言包 Release
（附件：Compositor-zh-Hans-langpack-v<版本>.zip
       + install-zh-Hans.command + restore-official.command）
```

所以你**只需要重新下载一次 `install-zh-Hans.command` 再双击**，
它会把新语言包覆盖进去（并且**不会**重复备份，原版备份始终是最初那一份）。
注意**每次下载的新文件都没有执行权限**（浏览器不会沿用旧文件的属性），
要按上面的两行再补一次；嫌烦就改下 zip，解压出来的一直能用。

<details>
<summary>也可以完全手动：只更新语言包文件</summary>

```bash
curl -fsSL -o /tmp/Localizable.strings \
  https://raw.githubusercontent.com/你的用户名/Compositor-zh-Hans/main/zh-Hans.lproj/Localizable.strings
cp /tmp/Localizable.strings \
  "/Applications/Compositor.app/Contents/Resources/zh-Hans.lproj/Localizable.strings"
xattr -cr /Applications/Compositor.app
codesign --force --sign - --deep /Applications/Compositor.app
```

（只换语言包文本时，`Info.plist` 不用再改，重签一次即可。）
</details>

---

## 能翻译到什么程度

这是本项目最需要说清楚的部分。

### 实测数据

对上游 v1.4.6 源码做的静态分析（用 `scripts/tools/analyze_coverage.py` 复现）：

| 类别 | 数量 | 外挂能翻吗 |
| --- | --- | --- |
| **A 类**：字面量直接写在本地化位置上<br><sub>`Text("Add Layer")`、`.help("Invert")`、`Label("New", systemImage: "plus")`</sub> | **423 个文案** | ✅ **能** |
| **B 类**：变量 / 表达式出现在同一位置<br><sub>`Text(title)`、`.help(help)`、`Text($0.rawValue)`</sub> | 205 处 / 95 种写法 | ❌ **不能** |

语言包 1253 条词条，对 A 类覆盖 **421 / 423 = 99.5%**
（剩下两个是空串和 `·`，本来就不该翻）。

这个数字是**精确核对**出来的，不是「差不多对上了」：工具会把每条源码文案按
SwiftUI 的运行时规则算成真实 key（`"Close \(x)"` → `Close %@`），
要求语言包里逐字符存在。CI 里 `scripts/tools/check-coverage-gap.py` 会在
缺口里出现任何一条**带实际内容**的文案时直接失败，不让它悄悄溜过去。

> **关于插值文案（27 条，也是最容易出错的一类）**
>
> 源码里写 `Text("Close \(tab.title)")`，运行时 SwiftUI 查的 key **不是**
> 那串源码，而是把插值换成格式符后的 `Close %@`。所以语言包里存的是
> `"Close %@" = "关闭 %@"` —— key 长得怪不是乱写，是 SwiftUI 就这么查。
>
> 两条实测规则（用 `swiftc` 反射 SwiftUI 内部的 key 得到，见
> `zh-Hans.lproj/Localizable.strings` 文件头）：
>
> 1. **格式符只由类型决定**：`String` → `%@`，`Int` → `%lld`，`Double` → `%lf`。
> 2. **永远不带序号** —— 不会有 `%1$@ × %2$@` 这种 key。
>
> 第 2 条踩过坑：语言包里曾有一批从别处抄来的 `"%1$@ × %2$@ px"` 形式的 key，
> 译文写得好好的，**运行时却永远查不到**，因为 SwiftUI 根本生成不出带序号的 key。
> 这类「死条目」已全部改掉；序号现在只允许出现在**译文**里，用来重排参数
> （`"%@ of %@." = "%2$@的%1$@。"`）。规则由 `check-strings.py` 第 7 条和
> `selfcheck.sh` 第 4 项把守。

### 为什么有些地方还是英文

因为拿不到那个「查表的机会」。

SwiftUI 里 `Text("Add Layer")` 和 `Text(name)` 看起来差不多，行为却完全不同：

```swift
let name = "Add Layer"

Text("Add Layer")   // 参数是字面量 → 编译器当成 LocalizedStringKey → 查表 → ✅ 显示「添加图层」
Text(name)          // 参数是 String   → 按原样渲染，根本不查表 → ❌ 永远显示 "Add Layer"
Text(verbatim: name) // 显式声明「不要翻译」
```

`name` 里就算存着 `"Add Layer"`，语言包里也有这条译文，**它也不会去查** ——
因为查不查表在**编译期**就由参数类型决定好了，运行时改不了。

要翻译这 205 处，只有一条路：**改源码，把它们包一层查表助手，然后重新编译整个 app**。
那是另一个项目要做的事（需要完整 Xcode 和一个 macOS 26 的构建环境），
不在「外挂语言包」的能力范围内。

**实际观感**：绝大多数界面（菜单、面板标题、工具栏提示、对话框、设置）都是中文。
仍有英文残留的地方主要是这几块，**全是 B 类，不是漏翻**：

- **工具选项栏的分段按钮**：`Rectangle / Ellipse / Line`、`Paint / Erase`、
  `Liquify / Blur / Smudge`、`Content-Aware / Create Texture / Proximity Match`、
  `Freehand / Polygonal`、`Wand / Object`、`New / Add / Subtract`、`Linear / Radial`、
  取样下拉的 `High quality`…… 源码全是
  `ForEach(...) { Text($0.rawValue) }`（B 类写法里出现最多的 `×33 $0.rawValue` 就是它）
- **图层面板右侧的两个下拉**：混合模式（`Normal / Multiply / Color Burn / …`）和
  新建调整图层（`Hue/Saturation / Curves / Gaussian Blur / …`）。
  混合模式那一份还是 AppKit 的 `NSPopUpButton.addItem(withTitle: mode.rawValue)`，
  选中时还要拿标题原文反解析回枚举 —— 更不可能走查表
- **菜单栏「图像 / 滤镜」里的一部分条目**：`Black & White…`、`Color Balance…`、
  `Exposure…`、`Gradient Map…`、`Grain…` 和整个「滤镜」菜单。源码写的是
  `Button("\(kind.rawValue)…")` —— 这是插值字面量，SwiftUI 查的 key 是 `%@…`，
  查到了也只会把英文 rawValue 填进去。所以同一个「图像」菜单里
  `曲线… / 色阶… / 色相/饱和度… / 反相` 是中文（字面量写法），其余是英文（rawValue 写法）
- 选项栏上的 `Expand` / `Contract`（按钮标题来自函数参数 `Button(title)`）
- 命令面板（⇧⌘P）里部分条目的名字

<details>
<summary>这几处为什么会这样（源码位置）</summary>

| 界面位置 | 源码 | 为什么翻不了 |
| --- | --- | --- |
| 选项栏分段按钮 | `Compositor/UI/ShapeControls.swift` 等：`ForEach(...) { Text($0.rawValue) }` | 枚举 rawValue 是 `String` 变量，走 `Text(String)` 原样渲染 |
| 混合模式菜单 | `Compositor/UI/BlendModePicker.swift`：`button.addItem(withTitle: mode.rawValue)` | AppKit `NSMenuItem.title` 不查 .strings，且 `LayerBlendMode(rawValue: $0.title)` 靠标题反解析 |
| 调整图层菜单 | `Compositor/Document/LayerAdjustment.swift`：`case curves = "Curves"` + `Text(kind.rawValue)` | 同上，rawValue 直传；且枚举值还要编码进文档文件，动了会坏兼容性 |
| 图像/滤镜菜单条目 | `Compositor/CompositorApp.swift`：`Button("\(kind.rawValue)…")` | 查表 key 是 `%@…`，插进去的内容仍是英文 rawValue |
| Expand/Contract 按钮 | `Compositor/UI/LassoControls.swift`：`modifyControl("Expand", …)` → `Button(title)` | `title` 是 `String` 参数，`Button(String)` 不查表 |

这些枚举的 rawValue 同时还是**文档格式的编码值**（`Codable`），就算改源码也得保持
rawValue 不变、另配 displayName —— 这也是外挂方案碰都不去碰它们的原因。
</details>

如果你在上面这些地方看到英文，那不是漏翻，是翻不了。介意的话……只能等上游把文案挪到字面量位置。

### 其他已知限制

- **命令面板（⇧⌘P）的搜索按英文匹配。** 界面显示中文，但要搜某个工具得输入英文关键词。
  这是搜索索引用了英文原文，同样属于要改源码才能解决的那一类。
- **约 85 条词条没有译文**，但基本都是噪音：`8BIM`、`TySh` 这类 PSD 二进制标记、
  纯数字读数、`MacBook` / `iPhone` 这类商品名，以及多行字符串被切碎的碎片。
  这些翻了反而会出错，所以刻意留在 `translations/never-translate.txt` 里。
- **不支持 Intel Mac。** 上游只发布了 arm64 版本。
- **装完后 app 不再是 Apple 公证的。** 因为内容被改过又用了 ad-hoc 签名，
  首次打开可能需要一次「右键 → 打开」（一键脚本会顺便清掉隔离属性，通常省掉这一步）。

---

## 常见问题

<details>
<summary><b>双击 .command 提示「无法打开，因为来自身份不明的开发者」</b></summary>

在文件上**右键 → 打开 → 再点一次「打开」**。这是 macOS 对未签名脚本的保护，只需放行一次。
</details>

<details>
<summary><b>双击 .command 提示「无法执行，因为你没有正确的访问权限」</b></summary>

浏览器保存下载文件时**不带「可执行」权限位**（`-rw-r--r--`），而 `.command`
双击运行的前提是有 `x` 位。跟脚本内容无关，zip 包里存的是 0755，直接下载附件才会遇到。

修复（终端里跑两行，或对照截图在「显示简介」里勾上「可执行」）：

```bash
chmod +x ~/Downloads/install-zh-Hans.command
xattr -d com.apple.quarantine ~/Downloads/install-zh-Hans.command 2>/dev/null
```

第二行顺手去掉隔离标记，免得接着撞上上一条 Gatekeeper 提示。
</details>

<details>
<summary><b>脚本报「没有权限修改 /Applications/Compositor.app」</b></summary>

macOS 13 起有「App 管理」保护：即使是 app 的所有者，也不能随便改 `.app` 内部。

打开 **系统设置 → 隐私与安全性 → App 管理**，把 **终端** 的开关打开
（列表里没有「终端」的话，先运行一次脚本让它出现），然后重新运行本脚本。

或者用管理员权限运行：

```bash
sudo bash scripts/install.sh
```
</details>

<details>
<summary><b>装完打开 Compositor 提示「已损坏，无法打开」</b></summary>

隔离属性没清干净。手动补一刀：

```bash
xattr -cr /Applications/Compositor.app
codesign --force --sign - --deep /Applications/Compositor.app
```

还不行就还原后重来：`bash scripts/restore.sh`，再重新安装。
</details>

<details>
<summary><b>装完界面还是英文</b></summary>

按顺序检查：

1. **退出并重新打开 Compositor** —— 语言包在启动时加载，开着的时候注入不会生效。
2. 确认语言包在位：
   ```bash
   ls -l /Applications/Compositor.app/Contents/Resources/zh-Hans.lproj/
   ```
3. 确认开发地区是 `zh-Hans`：
   ```bash
   /usr/libexec/PlistBuddy -c 'Print :CFBundleDevelopmentRegion' \
     /Applications/Compositor.app/Contents/Info.plist
   ```
4. 确认系统语言里有中文：**系统设置 → 通用 → 语言与地区**，
   「首选语言」列表里要有「简体中文」。
5. 还不行就还原后重装：
   ```bash
   bash scripts/restore.sh && bash scripts/install.sh
   ```
</details>

<details>
<summary><b>还原官方版之后，界面过几秒自己变回中文 / 新装官方版也是「部分汉化」</b></summary>

这是**旧方案的自动汉化守护**在作怪，不是本语言包的问题。

如果你以前用过别的注入式汉化包（比如 `skyecx/compositor-zh-hans` 的
`安装自动恢复.command`），它会往 `~/Library/LaunchAgents/` 里塞一个 LaunchAgent：
`com.wonderassembly.compositor.hanhua.plist`。它的 `WatchPaths` 同时盯着
`/Applications/Compositor.app` **和 `/Applications` 目录本身** —— 也就是说，
你往 `/Applications` 里放**任何**东西都会被唤醒，它随即把那份旧语言包重新注入并重签。

症状因此很有迷惑性：

* 还原官方版 → 几秒后界面自己变回中文，像是还原没生效
* 重新下载官方版装进去 → 装完就是半汉化的样子，像是「装不上官方版」
* 它注入的是**旧版**语言包（1209 条，比现在少 100 多条），所以成品是「部分汉化」

本仓库的 `install.sh` / `restore.sh` 现在会**先把它拆掉**
（移进 `~/Library/Application Support/Compositor-zh-Hans/legacy-removed/`，随时可搬回来）。
想手动处理：

```bash
launchctl bootout "gui/$UID/com.wonderassembly.compositor.hanhua" 2>/dev/null
mv ~/Library/LaunchAgents/com.wonderassembly.compositor.hanhua.plist ~/.Trash/
mv ~/Library/Application\ Support/CompositorHanhua ~/.Trash/
```

拆完再 `bash scripts/restore.sh --reinstall`，官方版就能装住了。
</details>

<details>
<summary><b>工具选项栏的 Rectangle/Ellipse、混合模式的 Normal/Multiply、部分菜单条目还是英文</b></summary>

这些**不是漏翻，是外挂语言包翻不了的那一类**（B 类，约 205 处）。
上面「能翻译到什么程度」一节有完整清单和源码位置。要点：SwiftUI 只对
**编译期写死的字面量**查表；枚举的 `rawValue`、函数参数传进来的标题都是
运行时变量，走原样渲染，永远不会查语言包。
</details>

<details>
<summary><b>语言包里明明有这个词条的译文，界面却还是英文，怎么回事？</b></summary>

那多半是 **key 没对上**，而不是没翻 —— 这类问题已经查清并修掉了。

SwiftUI 查表用的是**运行时算出来的 key**，不是源码里那串字面量：

| 源码写法 | 运行时的 key |
| --- | --- |
| `Text("Add Layer")` | `Add Layer` |
| `Text("Close \(tab.title)")` | `Close %@` |
| `Text("Current: \(w) × \(h) pixels")` | `Current: %lld × %lld pixels` |

于是有两种很隐蔽的「有译文但显示英文」：

1. **格式符类型写错** —— 源码插的是 `Int`，key 是 `%lld`，语言包却写成了
   `%@`。字符串看着几乎一样，运行时就是查不到。
2. **key 里带了序号** —— 写成 `"%1$@ × %2$@ px"`。SwiftUI **永远不会**
   生成带序号的 key，这种条目是死条目，译文再对也没用。

以前算覆盖率用的是「骨架匹配」（只看占位符出现在第几个位置），这两类错误
都会被算成「已覆盖」，所以一直没暴露。现在改成**精确核对**：

- 工具按上表规则把每条源码文案算成真实 key，要求语言包里逐字符存在
- `check-strings.py` 直接禁止 key 里出现 `%1$@`（序号只能写在译文里，
  用来重排参数，例如 `"%@ of %@." = "%2$@的%1$@。"`）
- 27 条插值文案的真实格式符登记在 `scripts/tools/key-type-hints.json`，
  不靠猜
- CI 与自检都会在出现「带实际内容的缺口」时直接失败

所以如果你现在还能看到某个词条有译文却不生效，**那就是个新 bug**，
欢迎带着截图提 issue。
</details>

<details>
<summary><b>会不会被官方更新覆盖回英文？</b></summary>

不会。安装脚本做了两件事：

- `SUEnableAutomaticChecks = false` —— 不再后台自动检查更新
- `SUFeedURL` 指向本仓库的空 appcast —— 就算你手动点「检查更新」，
  也只会得到「已是最新版本」

想恢复官方更新器，跑一次还原脚本即可。

代价是**你也不会自动收到官方新版本的提示**。想升级时就手动去
[上游 Releases](https://github.com/robbietilton/Compositor/releases) 装新版，
再重新双击一次 `install-zh-Hans.command`。
</details>

<details>
<summary><b>Intel Mac 能装吗？</b></summary>

不能。上游只发布了 arm64（Apple 芯片）版本，Intel Mac 上根本装不了官方 app，
语言包自然也无从附体。
</details>

<details>
<summary><b>这个语言包会动我的图片处理、色彩管理吗？</b></summary>

不会。语言包只是一份文本对照表，脚本只做「往 `Resources/` 里放一个文件夹」和
「改 `Info.plist` 里两个本地化键」这两件事。
`Contents/MacOS/` 下的可执行文件一个字节都没改。
</details>

<details>
<summary><b>图层名、文件名、文本图层的内容会被翻译吗？</b></summary>

不会。用户自己的数据（图层名、文档名、文本图层的文字）从来不经过界面文案查表，
不存在被翻译的可能。
</details>

<details>
<summary><b>术语用词跟 Photoshop 中文版一致吗？</b></summary>

尽量对齐。`translations/glossary.tsv` 是按 Photoshop 简体中文版的用词整理的术语表
（图层 / 选区 / 绘画 / 调整 / 变换 / 文字 / 界面 分组），共 259 条。
`translations/curated.tsv` 是 183 条人工校对的整句译文。
流水线补新词时**术语表优先**，所以用词会保持一致。

发现用词不统一或不符合 PS 习惯，欢迎[提 Issue](../../issues)，附截图最好。
</details>

<details>
<summary><b>这个语言包免费吗？安全吗？</b></summary>

免费，MIT 许可。所有脚本都是纯文本、可以直接读，
客户端不联网、不上传任何数据。

安装脚本唯一的网络行为是从本仓库下载语言包
（以及在你没装官方版时，从上游下载官方安装包）。

唯一的例外在 CI 那边：如果仓库维护者配置了 `LLM_API_KEY`，
流水线会用大模型翻译新增的界面短语，发出去的内容只有英文短语本身，不含任何用户数据。
</details>

<details>
<summary><b>我能自己改译文吗？</b></summary>

可以，两种方式：

- **只改本机**：直接编辑
  `/Applications/Compositor.app/Contents/Resources/zh-Hans.lproj/Localizable.strings`，
  然后 `xattr -cr` + 重签一次。（下次跑一键安装会被覆盖。）
- **让所有人都受益**：改 `translations/curated.tsv`（两列：英文 `<TAB>` 中文），
  提个 PR。下一轮同步会自动合进语言包。
</details>

---

## 反馈与贡献

- **汉化不对 / 有漏译 / 术语不统一** → [提 Issue](../../issues)，
  附上**截图**和你是在哪个位置看到的，最好再说明期望的中文用词。
  截图比文字描述好定位得多。
- **想改译文** → 直接改 `translations/curated.tsv` 提 PR。
- **发现某个英文残留靠语言包其实能修** → 那是我的分析漏了，
  请指出具体位置，我会补进语言包。

---

## 给维护者

<details>
<summary><b>仓库结构</b></summary>

```
Compositor-zh-Hans/
├── zh-Hans.lproj/
│   └── Localizable.strings          语言包本体（唯一的核心资产，1253 条）
├── 一键安装语言包.command             面向使用者的双击入口（薄壳）
│                                     └ Release 附件里叫 install-zh-Hans.command
├── 一键还原官方版.command             同上
│                                     └ Release 附件里叫 restore-official.command
├── appcast.xml                      空 feed，用来切断 Sparkle 自动更新
├── scripts/
│   ├── install.sh                   注入语言包 + 备份 + 改 Info.plist + 分层重签
│   ├── restore.sh                   还原（备份 → 就地拆除 → 从上游重装，三级降级）
│   ├── fetch-upstream.sh            下载上游源码 tarball（只为扫文案）
│   ├── make-langpack.sh             打包发布用的语言包 zip（内含上面两个脚本）
│   ├── set-repo.sh                  把 __REPO__ 占位符换成你的仓库地址
│   ├── selfcheck.sh                 提交前一键自检（10 项）
│   └── tools/
│       ├── extract_strings.py       全量扫描界面文案 + 与语言包做差集
│       ├── analyze_coverage.py      统计「外挂能翻多少」的权威口径（A/B 类，精确匹配）
│       ├── check-coverage-gap.py    缺口门禁：有带实际内容的文案没翻就退出码 1
│       ├── key-type-hints.json      27 条插值文案的真实格式符表（%@/%lld/%lf）
│       ├── translate_missing.py     术语表优先 + LLM 兜底
│       ├── merge_translations.py    把译文合并进语言包
│       ├── check-strings.py         校验格式 / 重复 key / 占位符一致性 / key 禁带序号
│       ├── update_state.py          写回 state/upstream.json
│       ├── make_release_notes.py    生成 Release 说明
│       └── lint-shell.py            shell 雷区检查（见下方「踩过的坑」）
├── translations/
│   ├── glossary.tsv                 术语表（259 条，按 Photoshop 中文版用词）
│   ├── curated.tsv                  人工校对译文（183 条）
│   ├── auto.tsv                     自动补译结果
│   └── never-translate.txt          确认不翻译的（91 条：PSD 常量、商品名…）
├── state/
│   ├── upstream.json                上游版本与本仓库统计
│   └── pending/untranslated.tsv     待人工处理的词条
└── .github/workflows/
    └── sync-upstream.yml            定时跟随上游 → 更新语言包 → 发 Release
```
</details>

<details>
<summary><b>本地开发与验证</b></summary>

```bash
# 拉一份上游源码（只为扫文案，不编译）
bash scripts/fetch-upstream.sh v1.4.6

# 看「外挂到底能翻多少」——这是最该关注的那个数字（精确匹配口径）
python3 scripts/tools/analyze_coverage.py _upstream --json build/coverage.json

# 看有没有「带实际内容」的缺口（有就退出码 1；CI 用的就是这一条）
python3 scripts/tools/check-coverage-gap.py build/coverage.json

# 看有哪些新文案没翻（全量口径，分母混着非 UI 常量，仅供参考）
python3 scripts/tools/extract_strings.py _upstream zh-Hans.lproj/Localizable.strings

# 补译 + 合并 + 校验
python3 scripts/tools/translate_missing.py
python3 scripts/tools/merge_translations.py translations/curated.tsv translations/auto.tsv
python3 scripts/tools/check-strings.py

# 提交前跑一遍自检（10 项，含 shell 雷区、ASCII 附件名与覆盖率）
bash scripts/selfcheck.sh --src _upstream
```

想启用 LLM 兜底翻译，本地这样跑：

```bash
LLM_API_KEY=sk-xxx LLM_MODEL=gpt-4o-mini python3 scripts/tools/translate_missing.py --llm
```
</details>

<details>
<summary><b>首次建仓要做的事</b></summary>

```bash
# 1. 把仓库里所有 __REPO__ 换成你的地址（幂等，跑两次也没事）
bash scripts/set-repo.sh 你的用户名/Compositor-zh-Hans
git add -A && git commit -m '设置仓库地址' && git push

# 2. GitHub 仓库 → Settings → Actions → General
#    Workflow permissions 选 "Read and write"
#    勾上 "Allow GitHub Actions to create and approve pull requests"
#    （不设的话 CI 没法提交语言包、也没法建 Release）

# 3. （可选）想启用 LLM 兜底翻译：
#    Settings → Secrets and variables → Actions
#      Secret:   LLM_API_KEY
#      Variable: LLM_BASE_URL（默认 https://api.openai.com/v1）
#      Variable: LLM_MODEL（默认 gpt-4o-mini）
#    不配也能跑：术语表命中的照补，其余留在 state/pending/ 等人工过。

# 4. 手动跑一次 Actions → Sync upstream translations
#    第一次会因为没有 lang-v* Release 而强制出一版，之后按上游版本走。
```
</details>

<details>
<summary><b>写脚本时踩过的坑（后来人会再踩一遍）</b></summary>

**① macOS 的 bash 是 3.2，会把 `$VAR` 后面紧跟的中文吞进变量名**

```bash
APP_VER="1.4.6"
echo "版本：$APP_VER（已汉化）"     # ❌ 变量名被解析成 "APP_VER（" → unbound variable
echo "版本：${APP_VER}（已汉化）"   # ✅
```

要命的是 **Linux 的 bash 5 完全没这问题** —— 所以 CI 全绿，只有用户双击时炸。
全仓库一律写 `${VAR}` 形式。`scripts/tools/lint-shell.py` 专门拦这个，已接进自检。

**② `set -euo pipefail` 下，命令替换失败会让脚本静默死掉**

```bash
SIG="$(codesign -dv "$APP" 2>&1 | awk ...)"   # 未签名时 codesign 返回非 0
```

`set -o pipefail` 之后整条赋值语句的退出码就是非 0，`set -e` 直接终止 ——
而且常常是在打印完 banner 之后，用户只看到标题就没了。
修法是末尾补 `|| true`，或者把值包进 `if`，让后面的判空和友好报错有机会执行。

**③ 占位符哨兵不能写成连着的字面量**

`set-repo.sh` 用 `sed` 全局替换 `__REPO__`。如果脚本里有一行是拿它做比较：

```bash
if [ "$REPO" = "__REPO__" ]; then REPO=""; fi
```

替换完就会变成 `if [ "$REPO" = "你的用户名/Compositor-zh-Hans" ]` ——
**拿真实仓库名和自己比**，于是正常传进来的 `--repo` 也被清空。

症状格外阴：本地手动跑完全正常（本地没跑过 set-repo），只有 CI 上炸。
写法是**两段拼接**，让 sed 匹配不到：

```bash
SENTINEL="__RE""PO__"
if [ "$REPO" = "$SENTINEL" ]; then ...; fi
```

`set-repo.sh` 替换完会立刻复查这个哨兵是否完好，坏了就硬失败。

**④ `grep -c` + `|| echo 0` 会输出两行**

`grep -c` 无匹配时打印 `0` 且以 1 退出，再 `|| echo 0` 就是两行 0，
后面 `[ "$n" -gt 0 ]` 直接报 `integer expression expected`。
改用 `grep -o ... | wc -l | tr -d ' '`。

**⑤ BSD grep 不支持 BRE 里的 `\|`**

macOS 上是 BSD grep，`grep 'a\|b'` 会静默无匹配（不报错！），
排查时能得到完全错误的结论。用 `grep -E` 或 `egrep`。

**⑥ YAML 的 `run: |` 里嵌 heredoc 要小心**

块标量会自动 dedent，一般没问题，但如果 heredoc 内容里有以 `*` 开头的行，
YAML 会把它当别名解析并报错。复杂的多行逻辑一律抽成独立脚本文件 ——
顺带还有个好处：能本地单独跑、单独测，不用每次都推上去看 CI。

**⑦ 自检脚本绝不能有副作用**

早期版本的 `selfcheck.sh` 会真的调用 `install.sh` 来验证参数守卫 ——
结果它把用户 `/Applications` 里的 app 重新注入并重签了一遍。
现在所有会改动真实安装的检查都改成静态检查，或者用不存在的路径确保提前退出。

**⑧ `codesign --verify --strict` 对带 Sparkle 的 app 会误报**

Compositor 内嵌 `Sparkle.framework`，而 strict 模式会对框架里的
`Versions/Current` 符号链接结构吹毛求疵 —— 连官方已公证的原版都过不了。
用普通的 `codesign --verify` 即可，它验证的正是我们关心的那件事：
签名与 bundle 内容是否匹配。

**⑨ `codesign -dv` 不输出签名主体，要 `-dvv`**

verbose 级别到 2 才有 `Authority=` 行。用 `-dv` 去 grep Authority 会永远拿不到值，
还原脚本因此会把「已恢复原厂签名」误报成「签名主体：未知」。

**⑩ GitHub 的 Release 附件名**只能**是 ASCII，中文会被悄悄改写**

这是本项目 CI 卡在「发布语言包 Release」很久的真凶。GitHub 官方文档在
[REST API → releases → assets](https://docs.github.com/en/rest/releases/assets)
的 Notes 里写得很清楚：

> GitHub **renames asset filenames** that have special characters, non-alphanumeric
> characters, and leading or trailing periods.

实测行为（用 `curl` 直传复现过）：

| 上传时的名字 | GitHub 实际存下来的 |
| --- | --- |
| `alpha.txt` | `alpha.txt` |
| `中文.txt` | `default.txt` ← 整段非 ASCII 变 `default` |
| `abc中文def.txt` | `abc.def.txt` ← 非 ASCII 段变一个 `.` |
| `一键安装语言包.command` | `default.command` |
| `一键还原官方版.command` | 422 `ReleaseAsset.name already exists` ← 和上面撞名了 |

而且它**不报错**，只在你下载到一个叫 `default.command` 的怪文件时才发现。
更严的还有：用 multipart `filename=` 或 RFC 5987 的 `filename*=UTF-8''…`
传中文名，会直接 `400 Invalid name for request`。

所以：**Release 附件名一律用纯 ASCII**；中文名保留在仓库文件名和 zip 内部
（zip 内部文件名不受这个限制）。`make-langpack.sh` 与 workflow 的
「组装发布物」那一步都带了断言，dist/ 里一旦出现非 ASCII 文件名就直接失败。

**⑪ SwiftUI 的本地化 key 永远不带序号，`%1$@` 形式的 key 是死条目**

语言包里曾有一批抄来的 key，长这样：

```
"%1$@ × %2$@ px" = "%1$@ × %2$@ 像素";
```

译文完全正确，但**运行时永远查不到** —— 因为 SwiftUI 的
`LocalizedStringKey` 在运行时只生成不带序号的格式符。别猜，这个结论是实测的：
用 `swiftc`（CommandLineTools 里就有，不用完整 Xcode）编译一小段代码，
再用 `Mirror` 反射 `LocalizedStringKey` 内部的 `key` 字段：

```swift
let s = "Rectangle"; let i = 42
dumpKey("Close \(s)")                    // -> "Close %@"
dumpKey("\(s) by 10")                    // -> "%@ by 10"
dumpKey("Current: \(i) × \(i) pixels")  // -> "Current: %lld × %lld pixels"
dumpKey("\(s) of \(s).")                 // -> "%@ of %@."      ← 不编号
```

**序号只允许写在译文里**（那是给 `String(format:)` 用来重排参数的，
`"%2$@的%1$@。"` 是合法的、也确实是这么用的）：

| 位置 | 允许带序号吗 |
| --- | --- |
| key | ❌ 绝对不行（写了就查不到） |
| 译文 | ✅ 要重排参数时必须用，且必须**全带**不能混用 |

顺带记一个容易漏的点：`String(format:)` 对位置参数支持没问题，
但 CFString 要求一个格式串里的占位符要么全带序号、要么全不带，
混用是未定义行为。两条规则现在都在 `check-strings.py` 里强制。

而之前之所以没暴露，是因为覆盖率用的是「骨架匹配」——只要占位符**位置**对上
就算翻好，格式符类型写错（`Int` 插值写成 `%@`）和带序号这两种错都照单放过。
现在改成精确匹配，并把 27 条插值文案的真实格式符登记进
`scripts/tools/key-type-hints.json`，不再靠猜。
</details>

---

## 许可与声明

- 上游 [Compositor](https://github.com/robbietilton/Compositor) 为 **MIT** 许可，
  版权所有 (c) 2026 Wonder Assembly LLC。
- 本仓库的语言包、脚本与译文同样以 **MIT** 发布，详见 [LICENSE](LICENSE)。
- 本项目与 Wonder Assembly LLC **无任何隶属或合作关系**，是非官方作品。
  完整声明见 [NOTICE](NOTICE)。

### 与上游的关系

上游作者已多次明确表示不接受本地化相关的 Pull Request
（[#57](https://github.com/robbietilton/Compositor/issues/57) /
[#74](https://github.com/robbietilton/Compositor/issues/74) /
[#123](https://github.com/robbietilton/Compositor/issues/123) /
[#205](https://github.com/robbietilton/Compositor/issues/205) /
[#222](https://github.com/robbietilton/Compositor/issues/222)），
历史上十几个本地化 PR 都没有被合并。

因此本项目**不向上游提交任何改动**，也不包含上游源码，纯粹以「外挂语言包」的形式存在。
如果哪天上游自己支持了中文，这个仓库就可以退役了。

> Compositor 的所有商标与版权归 Wonder Assembly LLC 所有。
