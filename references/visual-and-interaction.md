# 视觉风格、可视化模式与交互规范

本规范用于 `oil-diff` 步骤 3～5：设计每章的原生 HTML/CSS 可视化舞台，并维护暖纸书页风格、单行文件树与右侧原文对照抽屉的交互体验。上级流程见 [SKILL.md](../SKILL.md)。

## 一、 暖纸网页网格与「单页书纸」视觉语言

整套页面采用扁平微拟物（Flat-Skeuomorphic）的暖调纸张设计体系，兼顾工程网格秩序与长文阅读舒适度：

1. **底层画布与 `32px` 网页网格线（`.bg-grid` + `.bg-fade`）**：
   - 背景色 `--paper: #faf8f4`；
   - 全屏固定铺设 `32px × 32px` 暖墨细网格线（`rgba(38, 36, 33, 0.038) 1px`），顶部叠加暖琥珀柔光（`radial-gradient(ellipse 80% 50% at 50% -10%, rgba(242, 196, 90, 0.11), transparent 70%)`）；
   - 页面最大宽度 `1260px`，两侧与章节卡之间露出底层的 `32px` 网格线。
2. **独立书页卡片（`.paper-card`）**：
   - 表面色 `--page-sheet: #fffdf9`，将底层网格线隔绝在阅读容器之外，保证正文与图示零干扰；
   - 描边 `1px solid #e2d8c7`，圆角 `8px 12px 12px 8px`，带左侧微妙装订折痕内阴影（`inset 12px 0 0 -11px rgba(212, 198, 174, 0.35)`）与底部叠纸投影；
   - **禁止使用单侧粗左边框（`border-left: 3px/4px`）**：所有卡片、文件树行与提示均使用四边均匀的 `1px` 细边或柔和整块底色。
3. **暖墨与琥珀色彩体系**：
   - 正文主墨色 `--ink: #262421`，次级文字 `--t2: #57534c`，辅助文字 `--t3: #6e685f`；
   - 章节签（`§ 01`）、业务模块胶囊（`.module-badge`）、书页序号框（`.nav-number`）与文件树高亮统一使用暖琥珀金体系（`#8a6116` / `#f6ebd2`），不引入刺眼的彩虹多色编号；
   - 柔和砖红（`#9e3b24` / `#fbf1ee`）与松石绿（`#216343` / `#eef6f1`）仅用于表达「修改前 / 删除（`−M`）」与「修改后 / 新增（`+N`）」。

## 二、 配图是配图，文字是文字：6 类可视化舞台模式

每章必须包含一个 `.visual-stage` 可视化对比舞台。必须遵守两条铁律：

1. **配图里严禁塞段落文字（No Prose in Diagrams）**：
   - 解释性的句子统一写在配图上方的 `problem` / `example` 和下方的 `points` 里。
   - `<figure class="diagram">` 内部**禁止出现任何 `<p>` 段落或 `以前：…… 现在：……` 的长句说明**（`scripts/lint_report.py` 会直接报错拦截）；配图内的文字只能是 **2～10 字的极简短标签**（如 `× 粗黑实线轴`、`✓ 圆角无轴柱`、`× 双箭头重叠`）。
2. **图文 100% 对应，严禁拿无关假图凑数**：
   - 配图画的控件、图表或管道必须就是当前章节改的那件事（例如讲柱状图就画粗黑轴 vs 圆角无轴柱状图，讲下拉框就画双箭头挤压 vs 单箭头留白，不要放与章节无关的通用装饰图）。

优先在 `.oil-diff/assets/report-spec.json` 的每个章节项中使用结构化 `"diagram"` 字段，由 `scripts/render_report.py` 确定性生成：

- **`type: "routing"`（路由分流与文件架构图）**：传入 `beforeTitle`、`beforeFile`、`beforeNote`、`afterTitle`、`entryFile`、`entryTag` 与 `branches: [{"wire": "marketing|workspace|content|play", "title": "4～6字短名", "file": "文件名"}]`（卡片内只放线框缩略图 + 短名 + 文件名，不写长句）。
- **`type: "comparison"`（微缩界面正反对比）**：传入 `beforeTitle`、`afterTitle` 与可选的 `tableRows`。左侧展示高低不齐控件与混用黑框的反面窗口，右侧展示同行等高工具栏、分段滑块与对齐表格的正面窗口。
- **`type: "scenarios"`（三列纯视觉实物对照卡）**：传入 `cards: [{"kind": "chart|select|focus", "title": "4～6字短标题", "badTag": "× 6～10字痛点标签", "goodTag": "✓ 6～10字改后标签"}]`。每张卡只渲染上/下两个真实微缩控件盒与短标签，**零段落文字**。
- **`type: "flow"`（流程精简与并流图）**：传入 `beforeSteps: ["1. 短标签", "2. × 被删环节"]`、`startNode`、`tracks` 与 `endNode`（每个节点 `tag` 控制在 10 字以内）。
- **`type: "alignment"`（标尺对齐与取景工作台）**：展示 `120 px ≠ 240 px` 比例失调窗口与 `matchWidth: 240` 同比例缩放裁切窗口。
- **`type: "diagnostics"`（三段式检查管道）**：传入 `testFile` 与 `rows: [{"left": "源模块", "edge": "动作", "right": "目标规则", "verdict": "✓ 8 项全绿", "pass": true}]`。

如果需要编写更精细的自定义 `diagramHtml`，根据章节业务类型选用以下 6 种标准舞台模式（对应 CSS 类已内置于 [assets/report.css](../assets/report.css)）：

### 1. 流程精简与并流图（`.serial-flow` + `.parallel-flow`）
- **适用场景**：审批流、构建流水线、多阶段检查合并、串行改并行。
- **视觉构成**：上半区用 `.serial-flow` 横向展示原来的串行节点，被删减或合并的冗余节点加 `.is-removed`（自动渲染柔和斜线与红字痛点）；下半区用 `.parallel-flow` 展示起点分叉（SVG 分叉线 `.track-junction`）进入上下并行的 `.parallel-tracks`，再合流至右侧终点卡片。

### 2. 多场景对照矩阵（`.scenario-grid` + `.scenario`）
- **适用场景**：策略细化、按条件分情况处理、交互帧/缓存复用/重试次数调整。
- **视觉构成**：3 列并排卡片，每列展示一个具体场景的「以前做法（`.scenario-old`）」→「微缩实物示意（如 `.menu-filmstrip` 0ms/120ms/240ms 三帧展开、`.snapshot-grid` 局部虚线补拍、`.run-history` 执行记录对比）」→「现在做法（`.scenario-new`）」。

### 3. 标尺对齐与取景工作台（`.alignment-grid` + `.shot-window`）
- **适用场景**：图像处理、尺寸布局计算、坐标对齐、数据归一化。
- **视觉构成**：左侧 `.alignment-before` 展示比例失调的两个微缩窗口与 `.short-ruler` / `.mismatch-ruler`（如 `120 px ≠ 240 px`）；右侧展示参数胶囊（`.tool-options`）、对齐后的 `.ruler`、带绿色虚线取景框的 `.has-crop` 窗口，以及底部 `.stitched-result` 1:1 拼接成品。

### 4. 路由分流与文件架构图（`.domain-map` + `.route-columns`）
- **适用场景**：目录拆分、模块解耦、路由表重构、入口文件分流。
- **视觉构成**：左侧 `.legacy-file` 展示旧文件混装多类职责的痛点；右侧从 `.route-entry` 总入口引出树状连接线（`.route-columns` / `.route-branch`），指向带微缩页面线框图（`.domain-wire`）与真实文件图标（`.artifact-file`）的领域节点卡（`.domain-node`），直观标出 `新增` 文件、拆出的子文件与 `<del>` 已删除文件。

### 5. 微缩界面正反对比（`.workspace-comparison` + `.admin-window`）
- **适用场景**：UI/UX 规范升级、前后端组件改造、表单与表格字段优化。
- **视觉构成**：左侧渲染反面模板微缩窗口（`.fake-sidebar`、`.fake-metrics`、`.fake-table`），用 `.issue-pin`（`①～⑤` 圆点锚点）与底部 `.issue-legend` 标出具体问题；右侧渲染改进后的真实任务界面（`.real-sidebar`、`.real-toolbar`、带状态圆点的 `.status-tag` 以及带垂直对齐虚线的右对齐等宽数字列）。

### 6. 自动化检查防线卡（`.diagnostic-board` + `.diagnostic-row`）
- **适用场景**：新增单元测试、边界校验、Lint 规则、异常处理与守卫逻辑。
- **视觉构成**：每行左侧（`.diagnostic-input`）展示具体的错误输入样本或待检链路（如越界文件引用、入口路由链、失效章节标题），中间经箭头指向右侧判定徽章（`.test-verdict.verdict-fail` `× FAIL` 拦截说明，或 `.verdict-pass` `✓ PASS` 通过说明）。

## 三、 单行文件树、右侧原文对照抽屉与过渡动画

1. **右侧 Sticky 单行改动文件树（`.file-sidebar`）**：
   - 每个文件严格保持 `28px` 单行高度（`.tree-file`）：左侧为 VS Code 风格文件图标 + 文件名，右侧为等宽 `+N −M` 行数，无边框、无状态废话。
   - 随左侧正文滚动，属于当前章节的文件整行呈现柔和浅琥珀底色（`.is-current`，`#f6ebd2`）；当前被点击查看的文件呈现深琥珀胶囊（`[aria-current="location"]`，`#edd7a4` + `1px` 内阴影）。
2. **右侧滑出式原文对照抽屉（`.diff-drawer-root` / `aside.diff-drawer`）**：
   - 正文中的所有文件条均为 `<div class="diff-card"><button type="button" class="diff-file">`，**不在正文中原地向下展开代码**，确保左侧正文高度与滚动位置绝对稳定。
   - 点击正文文件条、右侧文件树、页尾文件清单或通过 `#diff-...` 锚点进入时，从视口右侧滑出 `720px` 宽的书页纸抽屉面板（滑入 `280ms`、滑出 `220ms`，缓动 `cubic-bezier(0.22, 1, 0.36, 1)`）。
   - 抽屉头部展示所属章节与要点上下文胶囊（`.drawer-context`）、文件图标与完整路径、`← 上一处 / 下一处 →` 切换按钮及 `✕` 关闭按钮；抽屉已打开时切换文件，对内部内容执行 `180ms` 淡入微移过渡。
3. **可中断 WAAPI 折叠控制器**：
   - 章底关联文件汇总条（`details.related-files`）、抽屉内的其余修改（`details.complete-diff`）、文件树目录（`details.tree-folder`）与页尾全部文件清单（`details.ledger`）共用 `assets/report.js` 中的可中断 Web Animations API 控制器（展开 `250ms` / 折起 `210ms`），并在 `prefers-reduced-motion: reduce` 下自动切换为瞬时响应。
