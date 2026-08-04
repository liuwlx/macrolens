# ML-20260804-004 Engineering-02 工作报告

## 1. 问题与场景

数据概览重构需要一个不读取业务指标表、不会误写生产数据、且每次启动结果一致的本地 Demo 数据面，同时认证用户与当前工作区仍必须来自真实数据库。Live 模式还必须能区分“从未入库”和“指定时点尚不可用”。原实现只有数据库驱动的指标读取路径，浏览器在整页为空时会统一返回冲突，无法支持安全、可重复的 UI 验收。

本任务范围限定在后端、分类种子注册表、远程开发脚本与对应测试；不启用数据提供方、不执行迁移或 seed、不写远程数据库，也不修改前端。

## 2. 分析过程

首先按组织规则核对任务卡、架构边界和不可覆盖 vintage 等数据约束。随后梳理公开读取契约，确定 Demo 和 Live 共用响应模型，并增加 `data_mode`、`availability` 和 CSV/HTTP 响应标记。P1 复核后进一步拆开两个边界：分类和指标 Demo GET 不构造业务读取 session；认证用户与当前工作区始终走真实 cookie 和数据库 session。测试以 exploding factory 证明前者，并以无 cookie 返回 401 且 auth session 被调用证明后者。

分类结构采用扁平注册表加 `series_codes` 所有权，启动时校验 61 个 canonical series 恰好各出现一次、父节点完整、无环且深度受限。稳定 ID 使用 UUIDv5，数值使用 canonical code 的 SHA-256 派生，时间固定到 `2026-08-01T00:00:00Z`。日/周/月/季分别从该时点向后生成 260/156/120/40 个已发布时间点并升序返回，从而保证跨进程确定性。

Live 空数据语义通过一次聚合查询取得每个 source 的最早 lifetime vintage，避免逐行查询：有当前值为 `available`，从未入库为 `not_ingested`，显式截止点早于最早 lifetime vintage 为 `not_available_as_of`。列表保持 200，单指标显式历史截止点按契约返回 409；从未入库的单指标返回 200 空数组。

## 3. 解决流程

1. 先写契约测试，记录 production 禁用 Demo、分类注册表缺失和 Demo 构造数据库 session 的 RED 失败。
2. 增加 `MACROLENS_DATA_MODE` 配置并禁止 production 使用 Demo。
3. 建立 61 指标的深层分类注册表、UUIDv5 稳定节点与启动期完整性校验。
4. 实现确定性 Demo provider，覆盖分类、浏览、详情、观察值、修订、分析、AI capability 与 CSV。
5. 为分类和指标数据读取依赖增加 Demo 无业务 session 分支；认证与工作区保持真实数据库依赖，并用中间件把非认证 mutation 统一阻断为 RFC 9457 风格 `409 demo_read_only`。
6. 为 Live 浏览和单指标读取增加 lifetime availability 聚合与精确空数据语义，保留许可和 source 状态。
7. 扩展 `remote-dev.ps1 Start -DataMode Demo|Live`，默认 Demo；两种模式都建立 SSH 隧道并探测 Alembic，以支持真实认证和工作区，状态文件记录 mode。
8. 刷新 OpenAPI 快照，执行 scoped lint/type、全量测试、脚本安全和 diff 校验。
9. P1 复核补齐 taxonomy 五类过滤透传；`scope=all&q` 每层只返回父节点的直系子节点，并按后代节点/指标匹配保留祖先、重算 direct/descendant counts。
10. 最终 P1 复核确认 Demo 仍查询真实工作区；若不存在则在任何 ORM 写操作前返回 `409 demo_read_only`，Live 继续自动创建并提交。

## 4. Agents、skills、tools 与文档

- Agents：Engineering-02 主席位单独实施；未创建子 Agent。Architecture 主席位提供公共契约，主线程与独立验收席位复核 Demo/Live/API 和 remote-dev 行为。
- Skill：使用 `tdd`，先建立 HTTP 与 CLI 可观察行为的失败测试，再最小实现并回归；阅读了该 skill 的 `SKILL.md`、`tests.md`、`mocking.md`。
- Tools：使用 `rg`/PowerShell 检索与检查，`apply_patch` 编辑文件，`pytest` 跑测试，`ruff` 做 scoped lint/format，`mypy` 做类型检查，仓库 OpenAPI 生成器刷新并校验契约，Git 检查 diff 和提交。
- 文档：完整阅读 `.codex/organization.toml`、`docs/organization/README.md`、根 `AGENTS.md`、`docs/architecture.md`，并参考 `docs/conclusions` 中既有远程数据库、部署和数据概览实施报告。

## 5. 可沉淀的经验与模式

- “Demo 指标读取不访问业务表”应由 exploding factory 证明；同时应单独测试认证 session 必然调用，避免把数据隔离误实现为匿名身份绕过。
- 只读模式中的“查询真实身份数据”不代表允许补写缺失数据；查询为空后的创建逻辑必须在构造 ORM 对象前按 data mode 分流。
- 演示数据的确定性需要同时固定 ID、随机源、时间锚点和频率边界，仅固定随机种子不够。
- 空数据不是一种状态。列表 API 应携带 availability，让 UI 可区分尚未采集与历史截止点之前不可用；单指标 API 再根据显式用户意图决定 200 空或 409。
- 可从一次批量 `min(vintage_at) group by source_series_id` 得到 lifetime 语义，避免浏览页 N+1。
- 本地安全默认值应是 Demo；但 Demo 仍需要真实认证，所以 Demo 与 Live 都保留隧道和 schema 检查。
- Windows 仓库测试读取 UTF-8 文件时应显式启用 `PYTHONUTF8=1`，依赖版本也应贴近仓库兼容基线，避免把环境漂移误判为代码回归。

## 6. 更好的初始提示词

> 请为 MacroLens 增加一个默认用于本地 UI 验收的只读 Demo 数据模式。Demo 的分类和指标读取不得创建业务数据 session，但认证 cookie、CurrentUser 与 CurrentWorkspace 必须始终查询真实数据库；当前用户无工作区时返回 `409 demo_read_only`，绝不自动创建。使用仓库 61 个 canonical series 构造固定时间、固定 ID、跨进程一致的深层分类和指标数据；日/周/月/季精确生成 260/156/120/40 点。taxonomy 搜索必须逐层保留匹配后代的祖先、每次只返回直系子节点，并与 provider/theme/frequency/unit/seasonal_adjustment 过滤一致。所有业务写接口在 Demo 返回 `409 demo_read_only`，production 禁止 Demo。Live 空数据要区分 available、从未入库和指定时点尚不可用，并避免 N+1。`remote-dev Start Demo|Live` 两种模式都建立 SSH 隧道并校验 Alembic。先写失败测试，更新 OpenAPI，跑完整后端测试、scoped Ruff/mypy，并提交工作报告；不要修改前端、不要迁移/seed、不要写远程数据库。

## 7. 更优方案反思与提示词

当前方案把 Demo facade 放在 API 路由边界，改动可控且能立即支持验收；更长期的方案是定义统一的只读查询端口，由 `SqlReadStore` 和 `DeterministicDemoStore` 两个适配器实现。这样路由无需逐个判断 mode，Demo/Live 的响应组装、许可策略和错误语义可共享，后续增加录制回放数据集也更自然。迁移应分阶段进行，避免本次为架构纯化扩大范围。

> 在不改变现有 HTTP 契约的前提下，把 MacroLens 的分类和指标读取抽象成一个只读 Query Store 接口，提供 SQL 与确定性 Demo 两个适配器，并让依赖注入在启动时选择实现。认证和工作区保留独立的真实数据库依赖。先用现有 Demo/Live 合同测试锁定行为，再逐路由迁移；保持所有 mutation 独立且 Demo 统一拒绝。SQL 适配器必须批量查询 availability，Demo Query Store 必须零业务数据库依赖。迁移完成后刷新 OpenAPI，执行完整回归，并证明两种 remote-dev 模式都保留认证所需隧道和 Alembic 校验。

## 验证记录

- `pytest backend/tests -q`（`PYTHONUTF8=1`）：132 passed。
- 最终 workspace P1 focused：`pytest backend/tests/test_demo_data_mode.py -q`，9 passed；Demo `add/commit/refresh` 均为 0，Live 各为 1。
- 本任务 15 个新增/修改 Python 文件 scoped `ruff check`：0 diagnostics。
- `mypy --follow-imports=skip backend/src/macrolens_api/demo_data.py`：0 issues。
- `mypy backend/src`：37 个既有错误，分布于 16 个历史 API/Worker 文件；本任务新增 Demo 模块无错误。本任务未扩 scope 修复这些基线债务。
- `python scripts/generate_openapi.py --check`：68 paths，current。
- OpenAPI 使用任务环境 FastAPI 0.116.1 生成；主工作区未锁定的 0.141.1 会产生框架级快照漂移，本任务未为该环境差异修改契约。
- `scripts/tests/remote-dev-static.ps1`：static and local process-safety contract PASS。
- `git diff --check`：PASS，仅有 PowerShell 文件未来 checkout 的 LF/CRLF 提示。
