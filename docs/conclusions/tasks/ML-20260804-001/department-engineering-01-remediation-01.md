# ML-20260804-001 / Engineering-01 Remediation 01 工作报告

## 1. 问题与场景

本次工作修复部署候选中的数据快照、浏览器性能、AI 上下文安全和 API 契约阻断项。主要风险是：观测与修订接口可匿名读取并可能绕过历史截止时间；浏览器在分页前加载全部历史；历史 AI 运行会混入无法按截止时间复现的上下文；校验错误不是 RFC 9457；AI 运行重试可能重复落库/入队；前后端树代码不一致；文档 AI 授权会把 provider 的 redistribution 标志误当成 AI 权限；AI 配置缺失时仍可能先持久化任务。

## 2. 分析过程

先依据任务卡逐项追踪路由、服务、Schema、SDK 和 Web 调用链，再检查数据读取是否都受同一个 `data_as_of` 约束。浏览器路径重点核对排序、分页和 `_points_by_source` 的先后顺序；AI 路径重点核对上下文快照、授权解析、配置检查、AIRun 与 Job 的事务边界。最后用静态契约断言和带假 Session 的聚焦单测覆盖无法依赖完整外部环境验证的边界。

## 3. 解决流程

1. 为 observations/revisions 增加用户与工作区依赖，统一规范化 `data_as_of`，只从 `ObservationVintage` 选择截止时间内每期最新版本，并让摘要与数值来自同一快照。
2. 浏览器先对元数据候选稳定排序并分页，只为当前页加载许可与历史；发布日期过滤只查询每个 source 的单条最新发布日期，facets 仍基于完整候选集。
3. 历史 AI 运行只允许可按截止时间复现的 series 上下文，其他上下文显式返回 `historical_context_unavailable`。
4. 注册 `RequestValidationError` 的 RFC 9457 problem-details 处理器。
5. 抽取不提交事务的 `reserve_job`，以工作区、用户和幂等键原文哈希形成唯一 reservation；请求体哈希不同返回冲突，相同请求返回原 AIRun，并把 Job 与 AIRun 放在同一事务提交。
6. 统一 API、导出和 TypeScript SDK 的默认树为 `macro-default`。
7. 文档 AI 上下文使用严格许可解析：最高优先级必须恰有一条有效策略，缺失或冲突均拒绝，不使用 provider redistribution fallback。
8. 抽取共享的 `ai_runtime_configured`，capability 与创建接口共用；创建接口在 reservation 和持久化前返回 503。
9. 更新 Web/E2E/SDK 的 Idempotency-Key 调用契约并补充 16 个聚焦回归测试。

## 4. Agents、skills、tools 与文档

- Agent：仅 `engineering-01`，未创建子 Agent。
- Skills：未使用额外 skill；本任务按项目组织规则和任务卡直接实施。
- Tools：`exec_command` 用于检索和检查，`apply_patch` 用于全部文件修改，协作消息工具用于向主线程汇报状态，`update_plan` 用于维护执行进度。
- 阅读文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260804-001/task-card.md`、根目录 `AGENTS.md` 注入规则。

## 5. 值得沉淀的经验与模式

- 时间旅行读取必须把“数值、摘要、修订、AI 上下文”绑定到同一个显式 cutoff，不能在任一层回退到 latest 表。
- 大列表接口应先完成纯元数据筛选、稳定排序与分页，再加载页内昂贵历史；跨页 facets 可独立基于完整 ID 集计算。
- 许可和历史可复现性都应 fail closed；provider 的通用发布能力不能隐式升级为 AI 使用许可。
- 幂等写入应先原子占用业务键，再在同一事务创建领域对象；同时保存规范化请求哈希以拒绝同键异参。
- capability 与 mutation 必须共享同一个运行时配置判定，mutation 仍需在副作用前再次检查。

## 6. 更好的初始提示词

“请审计并修复 MacroLens 的部署阻断项：所有 observations/revisions 数值接口必须登录并使用同一 `data_as_of` 从 vintage 表复现；浏览器必须先稳定分页再加载页内历史；历史 AI 上下文、文档许可和 AI 配置一律 fail closed；AI run 用显式 Idempotency-Key 原子去重；API 校验错误使用 RFC 9457；前后端与 SDK 统一 `macro-default`。请更新调用方、补聚焦回归测试、执行项目检查、区分环境/基线失败，生成七节结论报告并提交独立 commit。”

## 7. 更优方案反思与一次解决提示词

更优方案是把快照读取、许可决策、运行时能力和幂等 reservation 都建设成共享基础模块，并通过数据库集成测试验证真实 PostgreSQL 的并发冲突与窗口查询，而不是只在各路由分别补条件。后续还应为浏览器建立查询数预算测试，并在 CI 镜像中固定后端与前端完整依赖。

可直接使用的提示词：

“在 MacroLens 中建立四个可复用边界：`SnapshotQuery(data_as_of)`、严格 `LicenseDecision`、共享 `AIRuntimeCapability`、事务内 `IdempotencyReservation`。将 observations、revisions、browser、AI run/context 和 TypeScript SDK 全部迁移到这些边界；用 PostgreSQL 集成测试覆盖并发同键请求、每期 cutoff vintage、零/多条许可策略和分页查询数；用契约测试锁定 RFC 9457 与 `macro-default`；更新 Web/E2E，跑完 required checks，记录所有基线/环境失败，生成结论报告并提交。”

## 检查结果

- `pytest backend/tests/test_data_browser.py -q`：通过，16 passed。
- `python -m compileall -q backend/src backend/tests`：通过。
- 变更 Python 文件 `ruff --select F`：通过；核心新增文件完整 ruff：通过。
- 聚焦 mypy（10 个变更源文件，`--follow-imports=skip`）：通过。
- `npm --workspace packages/sdk-typescript run typecheck`：通过。
- `git diff --check`：通过。
- 全量 `ruff check backend`：未通过，运行时报告 389 个仓库既有格式/导入问题；本次新增代码的 F 类与核心文件检查均通过。
- 全量 `mypy backend/src`：未通过，运行环境缺少若干可选包并叠加仓库既有类型问题；聚焦变更源文件通过。
- 全量 `pytest backend/tests`：收集阶段因复用 venv 缺少 `jwt` 失败（6 个 collection errors）；聚焦回归通过。
- Web lint/test/build：当前 worktree 未安装完整 Web workspace 依赖，分别因 `eslint`、`vitest`、`next` 命令不可用而未执行；SDK typecheck 可用并通过。

## 剩余风险

- 浏览器对需要历史值的排序键采用“稳定元数据分页后页内排序”，满足历史加载预算，但不承诺全结果集按动态指标全局排序；若产品要求动态指标全局排序，应增加物化指标或专用汇总查询。
- 幂等并发路径已按 PostgreSQL `ON CONFLICT` 设计，但本环境缺少完整数据库依赖，仍建议 Integration/Release 在真实 PostgreSQL 上补一次并发验收。
