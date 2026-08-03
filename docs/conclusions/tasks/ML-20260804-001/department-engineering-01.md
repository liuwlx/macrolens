# ML-20260804-001 Engineering-01 工作报告

## 1. 问题与场景

数据总览页需要一组可直接供前端消费的后端契约：分类子节点、指标浏览器、批量及单指标导出、指标分析和 AI 能力提示，并同步 TypeScript SDK。场景同时受制于观测 vintage 不可覆盖、许可策略、工作区权限、快照可复现性、贡献版本血缘和批量查询性能等非功能约束。

## 2. 分析过程

先阅读组织规则、任务卡、完整实现计划和架构说明，再盘点现有 series/taxonomy/AI 路由、模型、许可解析和 SDK。识别出的主要风险是：旧指标搜索存在逐条许可和 latest 查询；`ObservationLatest` 不能满足快照；主数据源可能缺失或冲突；缺失许可会从 provider redistribution 标志推断；`SeriesDependency` 未绑定公式版本；导出可能产生部分文件或 CSV 公式注入；AI capability 只能作为提示，创建运行时仍须二次授权。

## 3. 解决流程

1. 新增 Pydantic 契约和批量数据浏览服务，一次加载候选指标、主数据源、taxonomy、alias、许可和 vintage 观测。
2. 所有数值快照查询限定 `ObservationVintage.vintage_at <= data_as_of`，按 source/period 选最新 vintage，并拒绝未来或不可复现的快照。
3. 对零个或多个已验证主数据源、缺失或同优先级冲突的许可策略一律 fail closed；display denied 不返回数值和发布时间元数据。
4. 新增 taxonomy children、series browser、browser export、single-series export、analytics、AI capabilities 路由；数值和导出路由要求当前用户及工作区。
5. 导出在写入首字节前完成全量许可检查，限制 10,000 行，固定文件名，增加 `nosniff`/`private, no-store`，并中和 spreadsheet formula 注入。
6. 贡献分析因当前依赖模型无法证明定义版本绑定而显式返回 `contribution_version_binding_unavailable`，不解析或执行 `weight_expression`。
7. `AIRunCreate` 增加 `data_as_of`；创建运行时冻结 cutoff，并在 `persist_contexts` 对 series 上下文重新检查当前工作区范围、唯一主源、display 和 AI 许可，再从 vintage 表生成快照。
8. SDK 增加严格类型及 taxonomy/browser/export/analytics/AI capability 方法，并新增后端安全边界单元测试。

## 4. Agents、skills、tools 与文档

- Agents：Engineering-01 独立实现；与主任务线程同步安全 P0 和检查状态，并协调 Engineering-02 的前后端字段契约。未创建子 Agent。
- Skills：本任务未触发可用 skill。
- Tools：`apply_patch`、PowerShell `exec_command`/`write_stdin`、协作消息、计划更新。
- 文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260804-001/task-card.md`、`docs/conclusions/2026-08-04-data-overview-complete-implementation-plan.md`、`docs/architecture.md`、根目录 `AGENTS.md`。

## 5. 可沉淀经验与模式

- 快照不是“查询时最新值”，而是请求开始即冻结的 cutoff 加上每个 period 的 latest-as-of 窗口查询。
- 许可解析必须显式处理优先级和冲突；缺配置不是公共许可，必须拒绝。
- capability 接口只能优化交互，所有真正产生数据或 AI 上下文的 mutation 都必须重新授权。
- 当关系模型缺少版本外键时，宁可结构化 unavailable，也不能把无版本依赖和任意公式拼接起来。
- CSV 安全包括完整授权、行数上限、公式注入、缓存和 MIME 防嗅探，不只是调用 `csv.writer`。
- 环境依赖不完整时，应尽快切换到 compileall、变更范围 lint 和 SDK typecheck，明确记录全量门禁阻塞，避免无限追逐安装。

## 6. 更好的初始提示词

请为 MacroLens 数据总览实现完整后端和 TypeScript SDK：新增分类子节点、指标浏览器、浏览器 CSV 导出、单指标 CSV 导出、指标 analytics 和 AI capability；所有数值接口需登录并绑定当前工作区，查询开始时冻结 `data_as_of`，只从 ObservationVintage 取 `vintage_at <= cutoff` 的每期最新版本；主数据源必须唯一且已验证，许可缺失或冲突必须拒绝；导出先全量授权再生成并防 CSV 公式注入；贡献依赖若不能证明公式版本绑定就返回结构化 unavailable，禁止执行 weight_expression；AI 创建运行时必须再次检查许可并保存同一 cutoff。同步 Pydantic、SDK 严格类型和回归测试，运行变更范围 lint、compileall、pytest、mypy 和 SDK typecheck，最后提交并报告 SHA 与环境阻塞。

## 7. 更优方案反思与一次解决提示词

更优方案是在共享的 catalog read model 中统一实现“唯一主源 + 有效许可 + as-of vintage”三项解析，并让 browser、analytics、export 和 AI context 只消费该 read model；同时在数据库层为有效主源、许可优先级和贡献 definition/dependency 版本建立可验证约束。这样能减少私有函数复用和 Python 侧全量过滤，并为游标分页、数据库 facet 聚合和可审计授权打基础。

一次解决的提示词：请先设计并实现一个批量 CatalogSnapshotReadModel，输入当前用户/工作区、筛选条件和 data_as_of，输出唯一已验证主源、明确有效且无冲突的许可、每期 latest-as-of vintage 与 taxonomy 元数据；所有 browser/analytics/export/AI context 路由必须复用它。数据库可证明不了的主源、许可或贡献版本关系一律 fail closed。分页、facet 和排序尽量下推 SQL；CSV 在授权完成后一次性缓冲并做注入防护；为相同 cutoff 的浏览、导出和 AI 快照一致性，以及冲突/缺失许可和主源写集成测试；同步 Pydantic/OpenAPI/SDK 后提交可 cherry-pick commit。

## 检查结果

- `py -3.12 -m compileall -q backend/src backend/tests`：通过（Python 3.12）。
- `npm --workspace packages/sdk-typescript run typecheck`：通过。
- 变更核心范围 `ruff`（data browser、AI router、新增测试）：通过。
- 全量 `ruff check backend`：失败；仓库基线含 alembic 生成 SQL 和既有模块的大量 E501/import 问题，本次未扩 scope 修复。
- 全量 `mypy backend/src`：隔离环境缺少完整运行时依赖，产生 123 个 import/stub 及既有类型错误；本次新增 Decimal 可空运算错误已据输出修复。
- `pytest backend/tests/test_data_browser.py -q`：隔离环境依赖安装受慢速/不稳定代理影响，最终在缺少 `email-validator` 时停止；测试文件已通过 compileall，需由集成环境补跑。
