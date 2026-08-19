# ML-20260820-048-WEB｜Web 批量历史同步 UI 结论

## 1. 问题与场景

MacroLens 后端提供了 TradingView Web 历史批次接口，但数据浏览器只有“数据同步”和单指标“同步历史数据”，管理员无法从页面启动全量候选历史回补，也看不到 339 个子任务的聚合进度。

本任务在数据浏览器增加管理员批量入口，使用后端 `HistoryBatchPublic` 契约直接展示批次聚合状态。范围仅限 Web；不修改后端、OpenAPI，不增加自动调度，不推送、合并或部署。

## 2. 分析过程

1. 读取项目规则、组织模型、领域上下文、本地开发宪法与 TDD 指引，确认本任务只覆盖开发链路阶段 01。
2. 从指定基线 `6e757bc0e644bbb7b6f99ecb8b942d7e0921df5e` 创建独立 worktree，隔离主工作区和其他工作者的未提交改动。
3. 检查 `data-browser-page.tsx`、公共 Web 类型、`apiFetch`、React Query key、已有 Vitest 和单指标历史同步测试。
4. 将事实与判断分开：
   - 事实：批量接口返回批次本身，不返回通用 `JobPublic`；轮询必须走批次 GET，不能走 `/admin/jobs`。
   - 事实：需求分别描述了“管理员且 live 时显示”和“TV 上下文时可用”。
   - 判断：按钮应在管理员 live 模式始终显示，在非 TV 上下文禁用并给出提示；不能把“不可用”误实现为隐藏。
   - 判断：`failed` 和 `partial_failure` 使用错误样式和失败标题，但仍展示聚合成功数量，以同时满足状态真实性和计数完整性。
5. 发现默认 shell 使用 Node 20.11.1，低于仓库要求且导致 jsdom 依赖加载失败；改用本机已安装的 Node 22.14.0 完成有效 RED/GREEN 和门禁，没有修改项目配置规避版本要求。

## 3. 解决流程

### TDD seam

- 用户点击“批量同步历史” → 只向 `/admin/providers/TRADINGVIEW_WEB/history` 发起一次 POST，body 包含稳定幂等键和 `limit: 500`。
- 批次响应 → 页面展示总数、排队、运行、成功、失败、历史点。
- queued/running → 每 2 秒调用批次 GET；终态 → 停止轮询并刷新相关查询。
- 页面卸载 → 取消待定计时器，不再发送批次 GET，也不再更新组件状态。

### RED

1. 首个组件测试因找不到“批量同步历史”按钮失败。
2. 第二个组件测试在推进 2 秒后仍显示初始 queued 数据，证明轮询尚未实现。
3. diff 复核后补充显示/可用语义测试；当前实现无法在管理员 live、非 TV 上下文找到禁用按钮，暴露了“隐藏”和“禁用”的契约差异。

### GREEN

1. 增加 `HistoryBatchStatus` 和 `HistoryBatchPublic` Web 类型。
2. 管理员 live 模式显示批量按钮；TV provider 筛选或当前选中 TV 指标时启用，否则禁用。
3. 每次页面执行过程生成一次幂等键，多次手动触发复用；每次点击只发一个 POST。
4. queued/running 每 2 秒轮询指定批次 GET，不访问 `/admin/jobs`；六类终态/活动状态均有明确文案。
5. failed/partial_failure 和网络/API 错误使用错误样式，不伪装成成功完成。
6. 到达终态后刷新 browser、detail、observations、analytics、taxonomy 五类 React Query 数据。
7. 卸载清理轮询计时器并通过 mounted guard 阻止后续状态更新；兼容 React Strict Mode 的 effect 重建。
8. 保留并回归验证原单指标“同步历史数据”。

## 4. Agents、skills、tools 与文档

### Agents

- 当前 Codex Web 实现线程：代码勘察、TDD、实现、测试、审查、报告与提交。
- 未使用子 Agent；任务修改面集中在一个组件、一份类型文件和相关测试，单线程可保持上下文与 TDD 纵向切片完整。

### Skills

- `tdd`：约束公共 seam、RED → GREEN、外部 API 边界 mock 和测试可维护性。

### Tools

- `exec_command` / `write_stdin`：读取文件、检查 Git/worktree、安装隔离 worktree 依赖、运行 Node 22 下的测试/检查/构建。
- `apply_patch`：创建和修改代码、测试及本结论报告。
- `update_plan`：维护实施与验证进度。

### 阅读文档

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `CONTEXT.md`
- `docs/governance/development-constitutions/README.md`
- `docs/governance/development-constitutions/01-local-development-and-freeze.md`
- `C:/Users/liuwl/.codex/skills/tdd/SKILL.md`
- `C:/Users/liuwl/.codex/skills/tdd/tests.md`
- `C:/Users/liuwl/.codex/skills/tdd/mocking.md`
- 相关 Web 实现与测试：`data-browser-page.tsx`、`types.ts`、`api.ts`、`auth-provider.tsx`、`browser-query.ts`、`metric-tree.tsx` 及现有 data-browser Vitest。

## 5. 值得沉淀的经验与模式

1. API 返回专用聚合对象时，前端应按专用批次状态机轮询，不要为了复用旧代码绕回通用任务列表。
2. “显示条件”和“可用条件”必须分别建模；尤其是管理操作，禁用按钮配原因提示能保留功能可发现性。
3. 长轮询至少需要三道边界：活动状态白名单、终态停止、卸载取消。mounted guard 还应考虑 React Strict Mode 的 effect setup/cleanup 重放。
4. 幂等键应按一次页面执行过程惰性生成并稳定复用，不能在每次点击或每次 render 时重新选择有效 key。
5. 失败状态可以包含成功子任务计数，但整体标题与视觉状态必须忠实表达 `failed` 或 `partial_failure`，避免“有成功计数”等同于“批次成功”。
6. 有效 RED 必须先排除运行环境故障；本次 Node 20 的 jsdom 加载错误不是行为 RED，切到仓库要求的 Node 22 后才获得可信测试证据。

## 6. 更好的初始提示词

> 请在 MacroLens 数据浏览器增加一个管理员批量回补 TradingView 历史数据的入口。管理员在 live 数据模式应看到按钮；筛选到 TradingView 或选中 TradingView 指标时按钮才可点击。点击后只启动一个后端批次，持续显示 339 个子任务的总数、排队、运行、成功、失败和历史点；运行中每 2 秒更新，结束后停止并刷新页面相关数据。失败必须明确显示失败。保留现有单指标历史同步，不做自动定时任务。请用现有 Web 测试体系先写失败测试再实现，并提交一个独立 commit，返回 RED/GREEN 和检查结果。

## 7. 当前场景的更优方案与提示词

当前方案已在允许修改范围内直接复用 React Query 和现有 API 边界，避免新增抽象文件，适合一次性页面能力。更优的一次解决方式是初始任务直接明确“显示”和“启用”的区别、终态集合、卸载语义及稳定 key 生命周期，避免中途语义返工：

> 从指定基线创建独立 worktree，只修改数据浏览器组件、Web 类型、相关 Vitest 和结论报告。先用 DataBrowserPage 公共组件 seam 写测试：管理员 + live 总能看到“批量同步历史”；仅当 provider=TRADINGVIEW_WEB 或选中 TV 指标时启用；一次点击只 POST 一次 `{idempotency_key, limit:500}`，同一组件挂载期间复用 key；queued/running 每 2000ms GET `/admin/providers/TRADINGVIEW_WEB/history/{batch_id}`；所有终态停止且不访问 `/admin/jobs`；聚合文案完整，failed/partial_failure 使用错误状态；终态刷新 browser/detail/observations/analytics/taxonomy；unmount 后不再 GET 或 setState。保留单指标同步。按纵向 RED/GREEN 实现，使用 Node >=22 运行目标测试、全量 Web tests、typecheck、lint、build，写报告并提交，不 push/merge/deploy。

## 8. 开发链路阶段与完成证据

- 已加载阶段：01 本地开发与候选冻结。
- 独立 worktree：`E:/workerspace/projects/20260709/macrolens-worktrees/ML-20260820-048-WEB`。
- 基线：`6e757bc0e644bbb7b6f99ecb8b942d7e0921df5e`。
- Web tests：14 个测试文件、50 个测试全部通过。
- TypeScript：`tsc --noEmit` 通过。
- Lint：0 error；2 个既有 warning 位于未修改的 `alerts/page.tsx` 和 `postcss.config.mjs`。
- Build：Next.js 16.2.12 production build 成功，14 个页面生成完成。
- Ruff：`ruff check backend` 通过。
- Mypy：`mypy backend/src` 通过，74 个源文件无问题。
- Backend pytest：按项目要求改用 Python 3.12.9 并显式加入 `backend/src` 后，333 个测试中 332 通过、1 失败。唯一失败为 `test_frontend_api_calls_are_represented_in_openapi`，指出基线 `macrolens_openapi.yaml` 尚未包含本任务按既定后端契约调用的两个 history batch 路径。任务明确禁止修改 backend/OpenAPI，因此该项必须由后端契约提交或集成发布阶段补齐后复验，Web 线程不越权修改。
- Docker：未启动或修改任何本地容器。
- 后端与远程服务：未修改、未启动、未连接；本任务使用测试边界验证前端契约。
- 阶段 02/03：未进入；未 push、merge、tag 或 deploy。

### 集成风险

- 指定基线不包含任务所述 history batch OpenAPI path；单独运行本 Web 提交时会触发上述前后端契约一致性测试失败。集成部门应先确认后端/OpenAPI 契约提交已进入目标分支，再 cherry-pick 本提交并复跑完整门禁。
