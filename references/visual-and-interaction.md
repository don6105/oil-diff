# 视觉风格、可视化模式与交互规范

本规范用于 `oil-diff` 步骤 3～5：设计每章的原生 HTML/CSS 可视化舞台，并维护暖纸书页风格、单行文件树与右侧原文对照抽屉的交互体验。上级流程见 [SKILL.md](../SKILL.md)。

## 一、 暖纸网页网格与「单页书纸」视觉语言

整套页面采用扁平微拟物（Flat-Skeuomorphic）的暖调纸张设计体系，兼顾工程网格秩序与长文阅读舒适度：

1. **底层画布与 `32px` 网页网格线（`.bg-grid` + `.bg-fade`）**：
   - 背景色 `--paper: #faf8f4`；
   - 全屏固定铺设 `32px × 32px` 暖墨细网格线（`rgba(38, 36, 33, 0.038) 1px`），顶部叠加暖琥珀柔光（`radial-gradient(ellipse 80% 50% at 50% -10%, rgba(242, 196, 90, 0.11), transparent 70%)`）；
   - 頁面寬度與兩側留白以 [assets/report.css](../assets/report.css) 的 `.report-layout` 為準。
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
   - 解释性的句子统一写在配图上方的 `overview` 和下方的 `points` 里。
   - `<figure class="diagram">` 内部**禁止出现任何 `<p>` 段落或 `以前：…… 现在：……` 的长句说明**（`scripts/lint_report.py` 会直接报错拦截）；配图内的文字只能是 **2～10 字的极简短标签**（如 `× 粗黑实线轴`、`✓ 圆角无轴柱`、`× 双箭头重叠`）。
2. **图文 100% 对应，严禁拿无关假图凑数**：
   - 配图画的控件、图表或管道必须就是当前章节改的那件事（例如讲柱状图就画粗黑轴 vs 圆角无轴柱状图，讲下拉框就画双箭头挤压 vs 单箭头留白，不要放与章节无关的通用装饰图）。
3. **真实截图防伪铁律（严禁拿网图或调研素材冒充实测图）**：
   - 只有当图片是本次改动实机运行/测试截出的真实画面、用户明确提供的实测图、或本身在本次 Git Diff 文件列表中时，才允许使用 `type: "screenshots"`（或卡片 `src`）。严禁从 `_work/`、调研参考夹或外部素材中抓取非本次实测的图片混入 Diff 汇报。

优先在 `.oil-diff/assets/report-spec.json` 的每个章节项中使用结构化 `"diagram"` 字段，由 `scripts/render_report.py` 确定性生成：

- **`type: "screenshots"`（真实实拍截图对比与拖拽滑块）**：
  - 优先用于 UI 改造、前端组件、可视化页面或 CLI 输出变更。将截图保存在 `<repo>/.oil-diff/assets/shots/`，在 `report-spec.json` 中使用相对路径 `assets/shots/xxx.png`。
  - 支持三种展示模式（`mode`）：
    - `mode: "slider"`（默认，需传入 `before: {"src", "title", "tag"}` 与 `after: {"src", "title", "tag"}`）：生成可左右拖拽的交互式滑块对比舞台（`.shot-slider`）与下方并排点击放大卡片；
    - `mode: "pair"`（传入 `before` 与 `after`）：生成左右并排的实拍窗口对照卡（`.shot-pair-grid`）；
    - `mode: "gallery"`（传入 `items: [{"src", "title", "tag", "state"}]`）：生成 2 列或 3 列实拍画面陈列卡。
  - 所有实拍截图默认绑定点击放大灯箱（`#shot-lightbox`），点击可全屏查看高清原图。
- **`type: "routing"`（路由分流与文件架构图）**：传入 `beforeTitle`、`beforeFile`、`beforeNote`、`afterTitle`、`entryFile`、`entryTag` 与 `branches: [{"wire": "marketing|workspace|content|play", "title": "4～6字短名", "file": "文件名"}]`（卡片内只放线框缩略图 + 短名 + 文件名，不写长句）。
- **`type: "scenarios"`（多列场景对照卡 / 性能指标卡 / 混合实拍对照卡）**：传入 `cards`（或 `scenarios`）：支持通用状态对照 `{"title": "短标题", "before": "旧行为", "after": "新行为", "badTag": "× 痛点", "goodTag": "✓ 改后"}`、性能/数值对比 `{"kind": "metric", "title": "耗时对比", "beforeValue": "320 ms", "afterValue": "28 ms"}`、UI 标本 `{"kind": "chart|select|focus", ...}`，单张卡也可直接传入 `"src": "assets/shots/xxx.png"` 与 `"captureSource"` 展示真实截图。每张卡**零段落文字**。
- **`type: "flow"`（流程精简与并流图）**：传入 `beforeSteps: ["1. 短标签", "2. × 被删环节"]`、`startNode`、`tracks`（或 `parallelTracks`）与 `endNode`（每个节点 `tag` 控制在 10 字以内）。
- **`type: "schema"`（数据结构 / API 载荷 / 配置字段对比）**：传入 `beforeTitle`、`afterTitle`，以及 `beforeRows: ["字段: 旧类型"]` / `afterRows: ["字段: 新类型"]`（或 `beforeFields: [{"key": "字段名", "val": "旧类型"}]` / `afterFields`），用于后端接口、数据库表结构、TypeScript 类型与 JSON 配置改动。
- **`type: "diagnostics"`（三段式检查管道）**：传入 `testFile` 与 `rows: [{"left": "检查项", "edge": "动作", "right": "目标规则", "verdict": "✓ 8 项全绿", "pass": true}]`。
- **`type: "comparison"` / `type: "alignment"`**：内置微缩后台正反对比窗口与像素标尺对齐工作台。

## 三、 可收起单行文件树、右侧原文对照抽屉与过渡动画

1. **右侧 Sticky 可收起单行改动文件树（`.file-sidebar`）**：
   - 窄栏宽度 `256px`，右上角提供 `收起 ⇥` 按钮（`[data-tree-toggle]`），点击后收起侧栏并在右上角浮出 `⇤ 文件树 (N)` 恢复按钮，释放全宽 Bento 画布。
   - 每个文件严格保持 `26px` 单行高度（`.tree-file`）：左侧为文件图标 + 文件名，右侧为等宽 `+N −M` 行数，无边框、无状态废话。
   - 随左侧正文滚动，属于当前章节的文件整行呈现柔和浅琥珀底色（`.is-current`，`#f6ebd2`）；当前被点击查看的文件呈现深琥珀胶囊（`[aria-current="location"]`，`#edd7a4` + `1px` 内阴影）。点击右侧文件树时**不触发主页面或文件树自动滚动**，避免当前点击项移位。
2. **右侧滑出式原文对照抽屉（`.diff-drawer-root` / `aside.diff-drawer`）**：
   - 正文中的所有文件条均为 `<div class="diff-card"><button type="button" class="diff-file">`，**不在正文中原地向下展开代码**，确保左侧正文高度与滚动位置绝对稳定。
   - 點選檔案或透過 `#diff-...` 錨點進入時，從視窗右側開啟原文對照抽屜。
     - 拖曳左側邊緣可調整寬度，並以 `localStorage` 記住結果。
     - 預設寬度與寬度限制見 [assets/report.css](../assets/report.css) 的 `.diff-drawer`。
     - 儲存功能不可用時，仍可在本次頁面調整寬度。
     - 拖曳「修改前 / 修改後」中間的分隔線可調整左右比例，每側至少保留兩成寬度。
     - 抽屜內所有原文對照沿用同一比例，窄螢幕維持上下排列。
     - 滑入 `280ms`、滑出 `220ms`，緩動為 `cubic-bezier(0.22, 1, 0.36, 1)`。
   - 抽屉头部展示所属章节与要点上下文胶囊（`.drawer-context`）、文件图标与完整路径、`← 上一处 / 下一处 →` 切换按钮及 `✕` 关闭按钮；抽屉已打开时切换文件，对内部内容执行 `180ms` 淡入微移过渡。
3. **可中断 WAAPI 折叠控制器**：
   - 章底外围同步文件折叠条（`details.related-files`）、抽屉内的其余修改（`details.complete-diff`）与文件树目录（`details.tree-folder`）共用 `assets/report.js` 中的可中断 Web Animations API 控制器（展开 `250ms` / 折起 `210ms`），并在 `prefers-reduced-motion: reduce` 下自动切换为瞬时响应。
