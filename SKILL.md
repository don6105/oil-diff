---
name: oil-diff
description: "将 Git 改动、提交范围或工作区修改生成直观易读的可视化 HTML 改动汇报页（含业务模块速览、前后对比图示、具体例子、单行改动文件树与右侧原文对照抽屉）。用户要求解释一轮代码或文档改了什么、把 git diff 做成汇报页或可视化演示页、向老板或团队展示仓库改动时使用。不用于执行代码修改、Git 提交、常规 Code Review 缺陷审计或制作通用幻灯片。"
license: MIT
compatibility: "核心采集、渲染与校验脚本只依赖 Python 3.10+ 标准库和系统 git 命令；生成的 HTML 汇报页为零外部依赖的单文件页面，可在现代桌面与移动浏览器直接打开。已在 macOS 实机验证，Windows 与 Linux 完成跨平台静态检查。"
metadata:
  version: "0.1.0"
---

# oil-diff

把零散的 Git 改动转化为非代码作者（如项目负责人、产品伙伴、协作者）一眼能看懂的**可视化改动汇报页**。以“让未参与编码的读者 30 秒内看懂改了哪块业务、原来有什么痛点、现在怎么运作、改了哪些文件”为唯一交付标准。

## 仓库安全底线与 `.oil-diff/` 目录约定

- 默认只在目标仓库下的未跟踪目录 `<repo>/.oil-diff/` 写入文件，第一步必须确认 `<repo>/.oil-diff/.gitignore` 内容精确为 `*` 加换行（自动让整个 `.oil-diff/` 对 Git 隐形，不修改目标项目根 `.gitignore`）。
- `<repo>/.oil-diff/index.html` 只放最终交付的自包含单文件汇报页；中间数据（`diff-data.json`）、业务归因规格（`report-spec.json`）及核验截图统一放入 `<repo>/.oil-diff/assets/`。
- 严禁执行 `git add`、`git commit`、`git checkout`、`git reset`、`git stash` 或修改任何已跟踪文件；交付前验证目标仓库的 `HEAD` 与 `git status --short` 和执行前完全一致。

## 先选择模式

| 模式 | 适用情况 | 路径 | 默认停止点 |
| --- | --- | --- | --- |
| 生成汇报 | 给定仓库、分支、提交范围或未提交工作区，首次生成汇报页 | 采集数据 → 业务归因与文案 → 构建图示 → 渲染 HTML → 校验 | 产出 `.oil-diff/index.html` 并通过校验 |
| 局部更新 | 已有 `.oil-diff/`，需调整章节划分、文案、图示或比较范围 | 读取现有配置 → 按需重跑采集或修改规格 → 重新渲染 → 校验 | 更新 `.oil-diff/index.html` 并通过校验 |
| 质量核验 | 已有 `.oil-diff/index.html`，只检查文案、结构与仓库边界 | 运行 `scripts/lint_report.py` → 按需用浏览器工具静态截图检查 | 输出核验结论后停止 |

下文的 `<python>` 指版本不低于 3.10 的 Python 解释器：macOS 与 Linux 通常使用 `python3`，Windows 通常使用 `py -3`。

## 执行工作流

### 1. 采集确定性 Git 改动数据

确定要汇报的仓库路径与比较范围（如未提交工作区、最近一轮提交，或 `base..head` 多段提交范围），运行 [scripts/collect_diff.py](scripts/collect_diff.py)：

```text
<python> scripts/collect_diff.py --repo <目标仓库路径> --output <目标仓库路径>/.oil-diff
```

需要指定多段比较范围时，传入一或多个 `--range <范围ID>:<显示名称>:<起点>..<终点>`（终点为工作区时写 `WT`）。脚本会自动创建 `.oil-diff/.gitignore`（写入 `*`）和 `.oil-diff/assets/`，并提取所有改动文件的路径、增删行数、行级修改块（hunks）及所在章节或函数上下文，保存为 `<output>/assets/diff-data.json`。

### 2. 按业务模块归因并撰写结构化文案

先完整读取 [文案与三层排版规范](references/copywriting-and-structure.md)。不要按文件列表逐个罗列改动，而是站在熟悉项目业务的汇报者视角，把全部改动文件归纳为 **3～7 件业务事项**，生成 `<output>/assets/report-spec.json`：

1. **业务模块与标题**：每件事必须标注简短的 `module`（业务模块胶囊，如 `工作区评审`、`截图工具 shoot.mjs`），标题遵循「所属业务模块/工具 + 具体动作 + 机制变化」，禁止写成脱离项目语境的泛泛常识句。
2. **背景痛点与生活化例子**：用平实中文说明原来怎么做、会遇到什么具体麻烦，并配一个一句就能懂的 `example` 日常场景，把作者自造缩写翻译为具体动作。
3. **具体改法要点与原文证据关联**：每件事拆分为 2～4 个改法要点（`points`），关联对应文件的核心修改行号。当一个要点下只有 1 个文件时，不写重复的 `.file-explanation` 摘要；外围顺手同步修改的文档统一归入章节底部的折叠汇总条。

若目标仓库改动较大，可将 `.oil-diff/assets/diff-data.json` 与两份参考资料交给独立子 Agent 起草或审校 `.oil-diff/assets/report-spec.json`，主 Agent 负责复核业务准确性。

### 3. 配置实拍截图与微缩可视化舞台（配图零段落）

先读取 [视觉风格、可视化模式与交互规范](references/visual-and-interaction.md)。在 `.oil-diff/assets/report-spec.json` 的每个章节项中配置结构化 `"diagram"` 对象（遵循「配图是配图，文字是文字」，`<figure class="diagram">` 内严禁出现 `<p>` 段落长句）：

- **优先嵌入真实截图（`type: "screenshots"` 或 `scenarios` 卡片的 `src`）**：当改动涉及页面 UI、终端输出，或项目/Agent 可通过浏览器工具截取画面时，将图片保存到 `<output>/assets/shots/`，使用 `"type": "screenshots"`（支持 `mode: "slider"` 拖拽滑块对比、`"pair"` 左右双图对比、`"gallery"` 多图画廊，以及点击放大 Lightbox）。
- **无实拍图时选用 5 类纯视觉积木**：从 `"type": "routing" | "scenarios" | "flow" | "schema" | "diagnostics"`（或 `"comparison" | "alignment"`）中选择与章节主题 100% 对应的结构化模式，由渲染器生成文件路由树、真实控件标本（柱状图/下拉框/焦点环）、流程并流图、数据结构/API 字段对比（`schema`）或三段式检查管道。
- 如需自定义 `diagramHtml`，必须包含微缩视觉图元且只放 2～10 字的极简短标签，严禁塞入 `<p>` 段落句子。

### 4. 渲染自包含 HTML 汇报页（Bento 看板与分类必看漏斗）

运行 [scripts/render_report.py](scripts/render_report.py)，将 `.oil-diff/assets/diff-data.json`、`.oil-diff/assets/report-spec.json` 与内置静态资源合成为单文件页面：

```text
<python> scripts/render_report.py --report-dir <output>
```

渲染器会自动校验所有改动文件是否均已归入章节、核对摘录行号是否存在，并嵌入 [assets/report.css](assets/report.css) 与 [assets/report.js](assets/report.js)，生成包含以下核心能力的 `index.html`：
- **默认 Bento 看板布局（`#bento-deck`）**：首屏通过紧凑模块卡片导航直达各章，主体采用双列 Bento 书页网格，高密度整合每章结论、实拍截图/架构图与改动要点，避免冗余重复文本；
- **按具体改动分类的「🎯 核心必看 / 📎 外围同步」漏斗**：在每个章节卡底部，将核心代码文件（`🎯 核心必看`）直接归类挂在 `1`、`2` 具体改法要点下方，将顺手同步的外围引用文件收进底部的 `📎 外围同步` 折叠条；
- **单行改动文件树与右侧原文对照抽屉**：点击任一核心文件胶囊、外围同步文件或右侧文件树，从右侧滑出 `720px` 代码对照抽屉。

### 5. 质量核验与视觉检查

渲染完成后，运行 [scripts/lint_report.py](scripts/lint_report.py) 执行静态质量与安全边界检查：

```text
<python> scripts/lint_report.py --repo <目标仓库路径> --report-dir <output>
```

- 校验器会检查：文风禁用词与机械兜底套话、单文件要点是否残留重复摘要、文件条是否全部使用右侧抽屉触发结构（`div.diff-card > button.diff-file`）、`.gitignore` 是否严格隔离、以及仓库 `git status` 是否未被污染。
- 若当前宿主提供浏览器工具，在桌面与窄屏尺寸下打开 `<output>/index.html`，截取静态图片检查首屏总览、各章 HTML/CSS 可视化舞台、单行文件树高亮以及点击文件条滑出右侧原文对照抽屉的效果。只用静态截图与 DOM 检查，不录制视频。

## 资源导航

- **参考规范**：
  - [references/copywriting-and-structure.md](references/copywriting-and-structure.md)：撰写章节标题、速览句子与编写 `report-spec.json` 前必读。
  - [references/visual-and-interaction.md](references/visual-and-interaction.md)：设计每章 HTML/CSS 可视化舞台与检查右侧抽屉交互前必读。

- **脚本与静态资源**：
  - [scripts/collect_diff.py](scripts/collect_diff.py)：步骤 1 采集 Git 改动并初始化 `.oil-diff/.gitignore`。
  - [scripts/render_report.py](scripts/render_report.py)：步骤 4 内联 [assets/report.css](assets/report.css) 与 [assets/report.js](assets/report.js) 生成 `index.html`。
  - [scripts/lint_report.py](scripts/lint_report.py)：步骤 5 校验文案、DOM 结构与 Git 零污染边界；修改脚本后运行 [tests/test_oil_diff.py](tests/test_oil_diff.py)。

## 输出与停止条件

当 `<output>/index.html` 生成完毕、`scripts/lint_report.py` 输出 `PASS`、且确认目标仓库的 Git 状态无任何新增修改时停止。向用户交付 `<output>/index.html` 的文件路径，并简要列出所归纳的业务事项标题与改动文件统计。
