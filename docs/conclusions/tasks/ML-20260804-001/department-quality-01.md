# ML-20260804-001 测试部 01 集成质量复核报告

- 席位状态：BLOCKED
- 任务 ID：ML-20260804-001
- 来源主线程：`/root`
- 起始提交：`b5ab5ed3cb2eec553bba4c4bc878c3abec5d0da8`
- 集成后端提交：`62a9d5626ffc10e74baa77e9af992e74dc1f3e11`
- 集成前端提交 / 当前 HEAD：`2e3484981c0696e960ec3b27cb78464454830b1c`
- 实际范围：只读审查集成 diff，运行 Node 24、SDK、Python 可用门禁，复核 browser/analytics/export/AI 合同、URL/分页/树/快照/响应式状态和测试；未修改业务代码。

## 1. 问题与场景

本轮在后端与前端候选已集成到 `main` 后执行独立质量复核。任务要求新版 `/data` 同时满足快照一致性、许可与工作区门禁、稳定分页、懒加载指标树、跨页面动作、响应式交互和可回滚性。因此静态类型或 build 绿色并不足够：趋势、历史、analytics、导出和 AI 必须实际共享同一个 `data_as_of`，树选择必须能驱动 browser API，查询规模也必须符合约 10,000 指标场景。

结论为阻断：发现 1 个 P0，以及多个 P1。当前候选不得进入完成态或以视觉通过覆盖合同问题。

## 2. 分析过程

1. 完整读取组织规则、任务卡安全修订、实施计划和两个集成提交。
2. 使用 `code-review` skill 将审查隔离为 Standards 与 Spec 两个只读子 Agent，再由测试部独立复核关键证据。
3. 使用隔离 Node `v24.18.1` 运行 Web typecheck、Vitest、production build、变更路径 ESLint 和 SDK typecheck。
4. 使用 Python 3.12 运行 compileall，并以 `uv` 在仓库外构建完整依赖环境尝试定向 pytest/ruff/mypy。
5. 逐项对照后端 Router、Pydantic Schema、服务、SDK、Web types/API 和组件状态；重点追踪同一 URL 状态与 `data_as_of` 是否真正到达后端查询。
6. 将任务开始前已记录的全仓 lint/Vitest/typecheck 历史基线与本次新增回归分开。

## 3. 解决流程、检查结果与发现

### 检查结果

| 检查 | 结果 | 说明 |
|---|---|---|
| Node 24 Web typecheck | PASS | 首轮与 build 并行时因 `.next` 竞争失败；build 后顺序重跑退出码 0，后者为有效结果 |
| Node 24 Web Vitest | PASS | 6 files / 15 tests 全部通过 |
| Node 24 Web production build | PASS | `/data` 静态路由生成；Next 自动生成/改写已精确清理 |
| Node 24 变更路径 ESLint | PASS | 仅审查本 diff 中现存 TS/TSX/MTS 文件 |
| Node 24 全仓 Web ESLint | 历史基线 FAIL | 55 errors / 4 warnings；任务开始前记录为 62 errors / 5 warnings。变更路径检查为 PASS，因此现存告警未判作本轮新增回归 |
| Node 24 SDK typecheck | PASS | 退出码 0 |
| Python 3.12 compileall | PASS | `backend/src`、`backend/tests` |
| Python targeted pytest | 环境构建中/未形成绿色证据 | 原宿主 Python 3.11 缺包；已用 `uv` 隔离构建 Python 3.12 完整依赖，不把 3.11 collection error 计为代码失败 |
| 全量 ruff/mypy/pytest | 未完成 | 本轮报告提交时无可复用项目环境；必须在整改候选上补跑 |
| E2E / 视觉 / 性能 | 未执行 | 当前 P0/P1 已先阻断；任务也尚未提供运行实例。视觉 QA 按主线程安排后置 |

构建会自动改写 `apps/web/tsconfig.json` 并生成 `apps/web/next-env.d.ts`。本席位曾精确清理自身构建副作用；报告收口时并行整改/构建再次生成了这两项变更，故未覆盖或删除并行线程资产。`artifacts/` 与其余任务文档同样不属于本席位。

### Standards

- **P1** `backend/src/macrolens_api/services/ai_context.py:162-261`：历史 `data_as_of` 只约束 series；document 仍取最高版本，release/FOMC/saved view/note 取当前态，但 `AIRun` 记录历史 cutoff。可把 cutoff 后证据混入历史 AI 快照，违反根 `AGENTS.md` 数据规则 6。
- **P1** `backend/src/macrolens_api/routers/series.py:62-213`、`taxonomies.py:19-31`：新增 Query/Path 校验仍由 FastAPI 返回默认 422；应用仅注册 `AppError` handler，没有把 `RequestValidationError` 转为 RFC 9457 problem details，违反根 API 错误规则。
- **P1** `backend/src/macrolens_api/routers/ai.py:44-98`：`POST /ai/runs` 没有客户端幂等键；重试会创建新的 run 和 job，违反“重试合理的 mutation 必须幂等”。
- **P2** `backend/src/macrolens_api/services/data_browser.py:509-584`、`backend/tests/test_data_browser.py:132-185`：latest-as-of SQL 只被 mock，未用 cutoff 前后多 vintage 的真实 PostgreSQL 数据证明窗口查询。
- **P2，judgement call — Speculative Generality** `data_browser.py:963-1115`：无条件 fail-closed return 后保留约 140 行不可达贡献实现；应删除，等 Schema 能证明版本绑定后再引入。
- **P3，judgement call — Duplicated Code** `taxonomies.py:67-90` 与 `data_browser.py:345-387` 重复树深度/规模受限遍历。

### Spec

- **P0** `apps/web/components/data-browser/analysis-panel.tsx:41-47` 把 `data_as_of` 发送给 observations/revisions，但 `backend/src/macrolens_api/routers/series.py:257-288` 不接收该参数；它被静默忽略，趋势/历史/修订实际混入 latest。旧 observations 数值路由也未绑定 `CurrentUser/CurrentWorkspace`。这直接违反 Security amendments #1/#4 和“同一快照”成功标准。
- **P1** `backend/src/macrolens_api/services/data_browser.py:653-685` 先对所有匹配候选加载每源最多 420 点并构建全部 item，最后才 `ordered[offset:offset+limit]`。10,000 指标默认 20 行可能处理约 420 万点，违反“先分页再批量取点”和 P95 预算。
- **P1** diff 未新增 data-browser E2E、五视口截图或 `design-qa.md`；Playwright 仍仅 Chromium desktop + Pixel 7，未覆盖 Firefox/WebKit、URL 恢复、许可/409、移动抽屉等任务要求。
- **P2** `data-browser-page.tsx` 的筛选、排序、分页、tab 多用 `router.replace`，不能形成计划要求的前进/后退操作历史；刷新通过独立 latest-check query，没有 invalidation 当前各区域。
- **P2** `browser-filter-bar.tsx` 没有页面级 `q` 搜索和 200–300ms debounce，只有树内本地搜索。

Spec 轴未确认实质 scope creep。

### 测试部独立新增发现

- **P1** 树代码不一致：`metric-tree.tsx` 与 seed 使用 `macro-default`，但 series browser/export Router 默认 `tree_code="macro"`，前端 browser/export 请求没有传 `tree_code`。选树节点后 descendants 查询会以错误树代码查找同一 UUID并返回 `taxonomy_node_not_found`，核心树筛选不可用。
- **P2** 公共合同未完全一致：后端贡献组件是单值 `value/unit/grouped`，Web 类型/图表期望 `values[]`；SDK 又用 `Array<Record<string, unknown>>`，违反计划“不用宽泛 Record 作为正式契约”。当前贡献被统一 fail closed，故缺陷暂被空数组掩盖。
- **P2** MetricTree 仅实现 ArrowLeft/Right、Home/End、Enter，未实现计划明确要求的 ArrowUp/Down；现有测试只覆盖点击展开和 ARIA tree，未覆盖键盘焦点移动。
- **P2** CSV 下载 Promise 没有 UI 错误处理；browser export 遇到全量许可 403/快照 409 时会产生未处理拒绝，用户看不到计划要求的许可/快照原因。

双轴汇总：Standards 6 项（最高 P1）；Spec 5 项（最高 P0）。测试部另补 1 个 P1、3 个 P2。

## 4. Agents、Skills、Tools 与文档

- Agents：测试部 01 主审；`standards_review` 子 Agent 只读检查仓库标准；`spec_review` 子 Agent 只读检查任务卡与实施计划。
- Skill：`code-review`。该 skill 强制把标准符合性和规格符合性隔离，避免绿色工具结果掩盖错误业务合同。
- Tools：`exec_command`、`write_stdin`、`apply_patch`、协作消息和 Agent 工具；`uv` 仅构建仓库外 Python 3.12 隔离环境。
- 已读：根 `AGENTS.md`、组织 TOML/README、任务卡、安全修订、完整实施计划、两个研发报告、集成报告、后端 Router/Schema/service/tests、SDK、Web API/types/data-browser 组件和测试、Playwright/Vitest/ESLint 配置。

## 5. 值得沉淀的经验或模式

1. `data_as_of` 出现在 URL、query key 和请求字符串中不代表快照已实现；必须追踪到 Router 参数和最终 SQL cutoff。
2. 全栈类型通过只能证明各自内部可编译；Web 独立类型、SDK 和 Pydantic 之间仍需自动生成或契约测试。
3. 树节点 UUID 不能替代树身份；`tree_code` 必须成为 URL/API/query key 的同一显式常量。
4. 稳定分页的性能边界应在 SQL 中发生。对所有匹配项计算后再切片，在小 fixture 上很容易伪装成正确。
5. build/test 并行会竞争 `.next`；质量流水线应先生成 Next 类型，再顺序执行 typecheck/build，或使用隔离输出目录。
6. 视觉 QA 不能覆盖安全、快照或查询复杂度阻断；应在合同绿色后执行。

## 6. 更好的初始提示词

> 请在同一冻结基线上实现并集成 MacroLens 数据浏览器。先定义唯一 `tree_code`、认证受众、`data_as_of` cutoff 和 Pydantic→OpenAPI→SDK→Web 自动合同；所有 browser、trend/history/revisions、analytics、export、AI context 都必须复用同一 latest-as-of-vintage 查询，并拒绝无法复现的快照。把筛选、排序和分页下推 PostgreSQL，先分页后批量取最多 420 点，并用 10,000 指标真实查询数/P95测试证明无 N+1。每个新参数错误返回 RFC9457；AI run 使用幂等键，所有上下文按 cutoff 复现或拒绝。完成 URL历史、树键盘、响应式抽屉、下载错误状态、E2E、五视口截图和feature flag回退后，再运行完整Python/Node门禁与设计QA。

## 7. 当前方案反思与更优方案提示词

更优方案是先建立一个认证的 `SeriesSnapshotReadModel`，由 browser、单指标趋势、修订、analytics、export 和 AI series context 全部调用；前端类型从 OpenAPI 自动生成，树代码由一个端到端常量提供。这样可从结构上消除当前“browser 快照正确、旧 observations 仍 latest”的分裂。

> 请先重构一个认证且 fail-closed 的 `SeriesSnapshotReadModel`：输入 user/workspace、唯一 tree identity、filters/pagination/sort 和 data_as_of，输出唯一主源、有效许可、latest-as-of vintages、facets 和分页行；trend/history/revisions/analytics/export/AI 只能通过该模型读取数值。先写 PostgreSQL 集成测试证明 cutoff 前后 vintage、20/100 行恒定查询数和 10k P95，再生成 OpenAPI/SDK/Web 类型。随后实现 URL push/replace 语义、完整树键盘和抽屉、许可/409错误反馈、Chromium/Firefox/WebKit E2E 与五视口视觉矩阵。任何匿名数值路径、静默 latest、未分页全量计算或 skipped 安全测试都阻断交付。

## 阻塞解除条件

1. 修复 P0：所有新版数值面板使用认证且支持 `data_as_of` 的快照接口；补匿名拒绝、cutoff 前后和 409 测试。
2. 统一 `macro-default`/`macro`，补真实树节点选择到 browser/export 的合同测试。
3. 分页下推并提供 10k fixture 的查询数与 P95 证据。
4. 修复 AI 非 series cutoff、RFC9457 validation 和 AI run 幂等性。
5. 补齐 targeted PostgreSQL tests、组件测试、E2E、视觉矩阵、性能与 `design-qa.md`。
6. 在 Python 3.12、Node 24 环境运行任务卡全部门禁，安全测试不得 skipped；将历史全仓 lint 与新增回归分别记录。

## 8. Remediation focused re-review（2026-08-04）

复核提交：后端 `d53c115`、桌面布局 `36f535b`、移动端/缓存隔离 `2acf33a`。本轮不修改业务代码，只复核原阻断的关闭证据并运行聚焦门禁。

### 原阻断关闭状态

- **原 P0 已关闭**：observations/revisions Router 现在同时要求 `CurrentUser`、`CurrentWorkspace` 并接收 `data_as_of`；服务层按 `ObservationVintage.vintage_at <= data_as_of` 读取，focused test 验证 cutoff 被原样传入 vintage 查询。
- **tree code P1 已关闭**：browser/export Router 与 TypeScript SDK 均统一默认 `macro-default`，focused contract test 通过。
- **AI 历史上下文 P1 已关闭**：显式历史 cutoff 下，不能证明版本边界的非 series 上下文返回 `historical_context_unavailable`，不再混入当前状态。
- **RFC 9457 validation P1 已关闭**：`RequestValidationError` 已注册 problem-details handler，focused test 验证 422 的 type/code/errors/location。
- **AI run 幂等 P1 已关闭**：`Idempotency-Key` 成为必填请求头；reservation key 同时包含 workspace、user 与散列后的客户端 key，同一 key/同一 payload 重放，异 payload 返回 409。
- **全量历史加载 P1 的性能部分已关闭**：数据点与许可只对 `matched[offset:offset+limit]` 页加载，focused test 证明 5 个候选、limit=2、offset=1 时只读取 source 2/3。
- **390px containment / 缓存隔离已验证**：静态 CSS containment test 与 AuthProvider 账号切换缓存清理 test 均包含在本轮 17 项 Web 测试中并通过。真实浏览器 document width 证据仍由主线程验收，不以静态测试替代。

### 新发现的阻断

- **P1，服务端数值/日期排序跨页错误**：`data_browser.py:701-732` 在 `current/change/period_change/yoy` 排序时，先按 search rank/UUID 切页，再只在当前页内 `_sort_items`，因此真正全局 top-N 可能落在后续页；`current_period` 虽在 `_sort_items` 映射中存在，却未包含在调用条件里，连页内排序也不执行。当前测试仅以 `sort="taxonomy"` 证明按页加载，未覆盖这一合同退化。必须在分页前得到全局稳定排序键（优先下推 SQL/物化读模型），并补跨页 top-N 回归测试，才能转为 PASS。

### 门禁结果

| 检查 | 结果 | 证据 |
|---|---|---|
| Python 3.12 focused pytest | PASS | `backend/tests/test_data_browser.py`: 16 passed，1 条 ORJSONResponse 弃用告警 |
| Python 3.12 compileall | PASS | `backend/src`、`backend/tests` |
| Node 24 Web Vitest | PASS | 8 files / 17 tests；含 390 containment 与跨账号缓存隔离 |
| Node 24 Web typecheck | PASS | 退出码 0 |
| Node 24 Web production build | PASS | `/data` 静态生成，退出码 0 |
| Node 24 SDK typecheck | PASS | 退出码 0 |
| 整改 Web 路径 ESLint | PASS / 历史例外 | 新增/整改组件路径通过；既有 `critical-path.spec.ts` 仍有历史 43 个 `no-explicit-any` |
| 全仓 ruff | 历史基线 FAIL | 386 项；整改核心新文件/新增代码未出现新的业务级 lint 回归，仓库既有格式债仍未清零 |
| 全仓 mypy | 历史基线 FAIL | 37 项 / 16 files；输出未指向本轮核心整改实现 |
| remediation diff check | PASS | `git diff --check 2e34849..HEAD` 无输出 |

### 复核结论

**BLOCKED**。原 P0 与原 Standards P1 已有聚焦证据关闭，但新发现的跨页数值/日期排序 P1 仍违反稳定服务端排序与分页合同。在该问题修复、跨页回归测试通过且主线程补充真实浏览器 document width 证据前，不得把本报告改为 PASS。
