# ML-20260804-001 前端返修 01 工作报告

## 1. 问题与场景

在 1536×1024 桌面验收视口中，当前数据概览页的下方分析区约从 y=699 开始，首屏表格约能看到 8 行；参考图的分析区约从 y=750 开始，表格区域更高。任务要求只修正 `>=1280px` 桌面布局的工作区首行高度，不改变平板、移动端、列宽、AppShell 或交互功能。

## 2. 分析过程

检查 `apps/web/app/globals.css` 后确认：默认 `.data-browser-workspace` 使用 `440px` 首行；`max-width:1279px` 使用 `470px`；`max-width:767px` 使用 `500px`。默认规则正是桌面端入口。把默认首行增加 60px，可将既有 y≈699 的分析区边界理论上推到 y≈759，接近参考图 y≈750，同时不影响两个窄屏媒体查询。

## 3. 解决流程

1. 核对组织规则、任务卡、基线提交和当前 worktree。
2. 仅将桌面默认规则的 `grid-template-rows` 从 `440px minmax(300px, auto)` 改为 `500px minmax(300px, auto)`。
3. 再次检查三处响应式规则，确认平板 `470px auto`、移动端 `500px auto` 未变化。
4. 使用 Node.js v24.14.0 安装锁定依赖，并运行类型检查、测试、生产构建和变更路径 lint。
5. 清理 Next.js 构建自动生成的 `next-env.d.ts` 以及对 `tsconfig.json` 的自动格式化，确保候选提交只保留目标样式和本报告。
6. 执行 `git diff --check` 并检查最终差异。

## 4. Agents、skills、tools 与文档

- Agents：研发部席位 `engineering-02`；来源主线程 `/root`。本次返修未派生其他子 Agent。
- Skills：本次窄范围 CSS 返修未重新调用 skill；实现约束直接来自返修任务卡和既有视觉验收测量。
- Tools：`exec_command` 用于只读检查、依赖安装和验证；`apply_patch` 用于 CSS 修改、构建生成物清理及报告创建。
- 已读文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260804-001/task-card.md`，以及目标样式文件 `apps/web/app/globals.css`。

## 5. 值得沉淀的经验

- 视觉位置偏差若能归因到明确的网格轨道，应优先修正单一布局变量，避免联动调整列宽、内边距和组件结构。
- 响应式 CSS 返修必须同时核对默认规则与所有覆盖规则，才能证明变更只影响目标断点。
- Next.js 构建可能自动改写 TypeScript 配置；提交前应清理生成差异，防止一次视觉修复夹带无关变更。
- 当前 ESLint 配置不解析 CSS。变更路径命令退出码为 0，但 CSS 质量主要由构建、差异检查和后续视觉验收保障；若需要真正的 CSS lint，应单独引入 Stylelint，而不是在本次窄范围返修中扩展工具链。

## 6. 更好的初始提示词

> 在 1536×1024 浏览器中，数据概览页下方分析区现在约从 y=699 开始，参考图约从 y=750 开始。请只把 `>=1280px` 桌面端数据浏览器工作区首行从 440px 调为 500px；不要修改 `<=1279px` 的 470px 规则、移动端 500px 规则、列宽、AppShell 或任何交互。使用 Node 24 运行 Web typecheck、现有测试、生产 build、变更路径 lint 和 `git diff --check`，清理构建生成物后提交。

## 7. 更优方案与一次解决提示词

当前方案已经是本场景风险最低的最小修复。更优之处在于把视觉测量、断点边界、允许修改的唯一属性及验证命令一次写清，并要求提交前证明窄屏规则未变：

> 基于已确认的 1536×1024 实测结果，修改 `apps/web/app/globals.css` 中默认 `.data-browser-workspace`：只将第一行 `440px` 改成 `500px`。修改后输出三处 `grid-template-rows` 的最终值，必须分别为桌面 500px、平板 470px、移动端 500px；预计分析区起点从约 699px 下移到约 759px。不要动任何其他视觉尺寸或功能。用 Node 24 完成 typecheck、全量现有 Vitest、production build、CSS 变更路径 lint 与 `git diff --check`，移除 Next.js 自动生成差异，只提交目标 CSS 和结论报告。

## 验证结果

- Node.js：v24.14.0。
- `npm --workspace apps/web run typecheck`：通过。
- `npm --workspace apps/web run test`：通过，6 个测试文件、15 条用例全部通过。
- `NEXT_PUBLIC_API_URL=/api/v1 NEXT_PUBLIC_DATA_BROWSER_V2=false npm --workspace apps/web run build`：通过，15 个页面路由生成成功。
- `npm --workspace apps/web exec -- eslint app/globals.css --no-warn-ignored`：退出码 0；仓库当前无 CSS parser，限制见上文。
- `git diff --check`：通过。
- 补充发现：全仓 Web lint 仍有基线遗留的 55 errors / 4 warnings，均位于未修改的 TS/TSX/MJS 文件；本返修未扩大范围处理。

## 风险与兼容性

变更仅影响宽度不小于 1280px 的数据浏览器工作区纵向尺寸，不改变数据请求、状态、交互、桌面列宽或窄屏抽屉规则。最终像素位置仍应由集成后的 1536×1024 浏览器截图复验。
