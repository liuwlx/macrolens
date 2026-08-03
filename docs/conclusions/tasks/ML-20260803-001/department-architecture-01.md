# ML-20260803-001 架构部执行契约设计报告

## 任务元数据

- 任务 ID：`ML-20260803-001`
- 角色：`PRIMARY`
- 部门席位：`ML | 架构部 | 01`
- 线程 ID：`019fc531-f5a2-7c91-ba58-7bfb4ca8ceeb`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 回执证据提交：`ab049e5`
- 实际范围：设计 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md` 之间无歧义、fail-closed、可机器校验的部门分派、回执、停止条件、路由与双层报告契约；不修改上述规则文件或校验器。
- 产物：本报告。
- 最终状态：`COMPLETE`（设计完成，等待知识管理部复核与研发部实现）

## 结论

建议将 `.codex/organization.toml` 定义为机器可读的唯一规范源（source of truth），`AGENTS.md` 保存所有 Agent 必须立即遵守的硬门禁，`docs/organization/README.md` 保存完整流程、路由示例与人工操作说明。三者共享同一 `contract_version`，校验器对配置结构、部门覆盖、触发器引用、文档版本标记和任务证据做 fail-closed 校验。

核心不变量是：除明确列入白名单的豁免动作外，任务默认是 substantive；每个 substantive task 在任何实质工作开始前必须有且仅有一个 `PRIMARY`、零个或多个 `SUPPORTING`，所有参与席位必须分别返回真实回执；主线程只能调度、记录和验收，不能替代部门执行，也不能事后补造回执或报告。无法匹配、无法取得空闲席位、回执缺失或证据不一致时，任务必须停在 `BLOCKED`。

推荐推理强度：治理设计、冲突判断和最终验收使用 `high`；按既定规则进行日常路由和回执核验使用 `medium`。推荐输出详细度：`medium`，但任务卡、回执、报告元数据必须完整，不能为了简短省略字段。

## 关键变更

1. **Change：将“实质任务”改为默认分类，豁免改为封闭白名单。Why：当前规则只提到 substantive task，却未定义边界。Impact：模糊任务不会绕过分派，分类不确定时自动进入分派流程。**
2. **Change：把“完整任务卡 + 全部真实回执 + 预工作证据提交”设为开工三重门禁。Why：仅在表格写 `RESERVED` 无法证明是谁、何时接受。Impact：Git 历史可以证明回执证据早于部门产物和实现提交。**
3. **Change：明确主线程的允许清单与禁止清单。Why：当前“主线程不长期直接编码”仍允许临时越权解释。Impact：主线程无法在无席位时静默接管，也不能代写部门证据。**
4. **Change：将部门路由分成领域所有权规则和可叠加的强制协作触发器。Why：任务类型表无法覆盖混合任务。Impact：一个任务可根据多个风险同时拉入架构、数据、测试、安全、集成等部门。**
5. **Change：建立每任务目录、部门报告、主总结三类结构化证据，并让校验器验证路径、身份和状态一致性。Why：普通 conclusions 报告不能可靠关联分派和结果。Impact：从任务卡到回执、部门结果、集成和总结形成可审计链。**
6. **Change：TOML 保存稳定 Schema 和规则标识，Markdown 只保存同版本的人类说明。Why：让校验器解析自然语言会脆弱。Impact：规则变更可由字段和 ID 精确检查，文档漂移可通过版本标记发现。**

## 1. 本次遇到的问题以及场景

MacroLens 已有四个平级主线程、共享部门池、席位状态、任务卡、worktree 和集成约束，但当前合同存在以下空档：

- `substantive task` 没有操作性定义，主线程可以把设计、只读复核或小改动解释成非实质任务。
- 只要求任务卡列出部门，没有规定“有且仅有一个主责”、各席位分别回执以及回执必须先于工作。
- `RESERVED` 只是状态，没有标准字段、真实来源和时序证据。
- 没有匹配部门或没有空闲席位时，现有规则没有明确禁止主线程接管。
- 推荐调度组合是示例表，不是覆盖所有部门的强制路由合同；混合风险任务可能漏派。
- 部门报告和最终结论没有按 task ID 建立一一对应关系，也没有区分部门事实与主线程汇总。
- `.codex/organization.toml` 只描述组织容量，尚不足以驱动机器校验。

本任务要求在不改变“模块化单体、常驻 local、编码才 handoff worktree、集成发布部唯一整合者”等既有原则的前提下补齐这些门禁。

## 2. 分析这个问题的过程

### 2.1 事实核对

1. 当前 TOML 已声明 4 个主线程、26 个部门席位、11 个部门、5 种席位状态和 `main_threads_may_implement = false`。
2. 当前 README 已规定任务卡字段、席位状态、推荐组合、Git 流程和部门交付格式。
3. 当前 `AGENTS.md` 已规定部门必须先读组织规则、一个席位只能占用一个任务、编码时才进入独立 worktree，并保存数据与安全不变量。
4. 当前仓库只有 `scripts/validate_repository.py`，任务卡要求的 `scripts/validate_organization.py` 尚不存在。
5. 当前任务的架构部回执已由来源主线程记录在提交 `ab049e5`，因此本报告的工作开始具有先行证据。

### 2.2 设计判断

- **分类必须默认关闭逃生口。** 不应维护容易漏项的“哪些任务算实质”关键词表；应定义宽泛正例，再用极窄豁免白名单排除纯初始化与纯协调动作。无法判断时按 substantive 处理。
- **证据必须同时解决身份和时间。** 报告中声称“之前已经回执”不够；回执必须来自被派发线程，来源主线程必须在开工前把回执元数据落入任务卡并形成 Git 提交。后续报告和实现提交引用该 SHA，校验器检查祖先关系。
- **路由规则必须可合并。** “任务类型到部门组合”的单选映射会在 API + AI + 权限等混合任务上失效；应先选一个核心结果所有者作为 PRIMARY，再把每个风险触发器要求的部门并入 SUPPORTING 集合。
- **机器校验不应解释散文。** TOML 应保存枚举、必填字段、路径模板、部门代码和触发器；Markdown 只需声明相同版本并包含规定章节。
- **主总结不是部门报告。** 主线程可以汇总已存在的证据，却不能创造部门结论。某个部门未交付时，summary 只能标为 `BLOCKED`，不能用主线程文字填补。

## 3. 解决这个问题的工作流程

### 3.1 规范优先级与跨文件职责

按以下优先级处理冲突：

1. 根目录 `AGENTS.md`：运行时硬约束和禁止动作。
2. `.codex/organization.toml`：组织执行合同的机器可读唯一规范源。
3. `docs/organization/README.md`：对 TOML 的人类可读解释和示例，不得新增与 TOML 冲突的例外。
4. 具体 `task-card.md`：只能收紧当前任务范围和检查，不能放宽前三者。

三个组织文件必须声明相同的整数 `contract_version`。版本不一致、TOML 无法解析、文档缺少版本标记时，任何新 substantive task 均不得开始；已有任务只能做停止、保存现场和报告阻塞所必需的动作。

### 3.2 substantive task 与豁免

**substantive task 定义：** 满足以下任一条件即为实质任务：

- 创建、修改、删除或生成仓库文件、代码、配置、Schema、迁移、测试、数据、文档或结论产物；
- 改变 Git、worktree、外部系统、部署、凭据、任务状态以外的持久状态；
- 形成会被后续实现或验收依赖的需求、设计、架构、数据口径、安全结论、研究结论、测试结论、发布判断或正式审查；
- 执行正式验证、故障诊断、数据审计、代码审查、集成、发布或回滚；
- 用户或来源主线程明确要求任务卡、部门交付物、commit、报告或可复用结论。

**唯一豁免白名单：**

- 新常驻线程仅完整加载组织规则、确认身份并返回 `席位状态：IDLE`；
- 席位对派单只返回 `RESERVED` 或 `BLOCKED` 标准回执，且不开始分析或实施；
- 主线程只查询席位状态、读取既有回执/结果、发送调度消息或报告简短进度，不形成领域判断；
- 用户只询问某个已记录任务的机械状态，回答完全来自现有证据且不新增分析结论。

豁免动作不得修改项目文件、创建 worktree、提交代码、形成领域结论或代替任何交付物。未明确落入白名单，或对是否豁免存在分歧时，必须按 substantive task 处理。

### 3.3 主线程允许与禁止动作

**允许：**

- 读取仓库和线程事实，澄清目标，建立任务 ID 和完整任务卡；
- 根据路由规则选择 PRIMARY 与 SUPPORTING，核对席位状态，发送派单请求；
- 原样接收并记录回执，提交预工作分派证据；
- 调度依赖、监控状态、向用户报告阻塞、验收已有部门结果；
- 维护当前任务的 `task-card.md` 和最终 `summary.md`；
- 请求集成、测试和补充复核，但不得替它们下结论。

**禁止：**

- 亲自执行本应由部门完成的需求、设计、实现、测试、审查、集成或部署；
- 在没有匹配/空闲席位时自行接管，或把其他主线程及其席位重新排序；
- 代部门生成回执、部门报告、线程 ID、检查结果、commit SHA 或通过状态；
- 在部门开始后补写“此前已分派”的记录，或把事后确认冒充开工前回执；
- 合并、推送或部署，除非更高层用户授权且组织合同明确允许；即使授权，也不能跳过强制部门验收。

`main_threads_may_implement = false` 应作为无例外机器不变量。若未来要改变，必须升级 `contract_version`，不能通过单张任务卡覆盖。

### 3.4 单一主责、多协作部门与标准回执

每个 substantive task 必须满足：

- 恰好一个 `PRIMARY`；PRIMARY 对核心交付结果和范围完整性负责。
- 零个或多个 `SUPPORTING`；每个 SUPPORTING 有互不含糊的 accepted scope。
- 同一席位在同一任务只能出现一次；同一席位同一时间只能服务一个 active task。
- 所有强制触发器要求的部门都必须进入参与集合；触发器只增加部门，不能移除已命中的部门。
- 每个参与席位有唯一报告路径 `docs/conclusions/tasks/<task-id>/department-<department-code>-<seat-number>.md`。

派单分两步，且不得合并为“派单并立即工作”：

1. 来源主线程发送只回执请求，内容包含完整任务卡路径、role、accepted scope、report path 和“禁止开始工作”。
2. 部门读取前置规则与任务卡，只返回以下标准键值。成功接受时必须逐字段填写：

```text
status=RESERVED
task_id=ML-YYYYMMDD-NNN
role=PRIMARY|SUPPORTING
thread_title=<已分配线程的真实标题>
thread_id=<已分配线程的真实 ID>
accepted_scope=<该线程承诺的范围>
report_path=docs/conclusions/tasks/<task-id>/department-<department-code>-<seat-number>.md
```

无法接受时返回：

```text
status=BLOCKED
task_id=<task-id 或 UNKNOWN>
role=<role 或 UNKNOWN>
thread_title=<真实标题>
thread_id=<真实 ID>
reason=<缺失字段、占用、无权限、范围冲突或其他事实原因>
```

只有来自任务卡所列 `thread_id` 的真实回复才是有效回执。来源主线程必须把全部回执字段记录到任务卡的结构化元数据，提交该记录，并把提交 SHA 记为 `receipt_commit`。所有参与部门都有效 `RESERVED` 且 `receipt_commit` 已存在后，主线程才能发送第二条“开始工作”消息。

### 3.5 fail-closed 停止条件与禁止事后造证

以下任一条件成立，状态必须为 `BLOCKED`，且只能进行收集缺失信息、保存现场、报告阻塞等恢复动作：

- 任务卡缺少 task ID、来源线程、目标、成功标准、范围内/外、依赖、检查、交付物或阻塞条件；
- PRIMARY 数量不等于 1；强制触发部门缺失；角色、范围或报告路径重复/冲突；
- 匹配部门不存在、对应部门没有可用 `IDLE` 席位、席位已绑定其他 active task；
- 任一参与席位未回执、回执为 `BLOCKED`、回执身份与任务卡不一致；
- `receipt_commit` 不存在、不是当前任务卡的提交、不是后续部门/实现提交的祖先；
- 工作环境不符合约束，例如只读分析提前创建 worktree，或两个编码线程共享 worktree；
- 必须检查无法运行且任务卡没有明确的可接受替代证据；
- 组织合同版本不一致或校验器失败。

**禁止补造规则：** 工作开始后才出现的回执只能标记为 `late_receipt`，不能使该次执行合规。发现缺失时必须停止当前执行，把已有产物标为 `UNVERIFIED`，由来源主线程创建新的执行轮次或新任务 ID，重新完成分派和预工作证据提交。主线程不得复制部门旧消息、改写时间、代填身份或仅修改 Git 历史来宣称先前合规。

### 3.6 部门路由与强制协作触发器

先按“核心结果最终由谁负责”选择一个 PRIMARY，再把下列命中的部门全部加入 SUPPORTING；若某强制部门已是 PRIMARY，不重复添加。关键词只能辅助，实际文件、数据流、权限边界和验收责任才是判定依据。

| 部门代码 | 领域所有权 / 可作为 PRIMARY 的场景 |
| --- | --- |
| `product` | 用户问题、产品范围、工作流、优先级、体验和产品验收标准 |
| `architecture` | 模块边界、公共接口、Schema、数据流、跨模块技术决策和 ADR |
| `data_sources` | 官方 Provider、来源映射、解析、回填和官方来源口径 |
| `data_platform` | vintage、血缘、质量门禁、发布批次、派生公式、数据库任务、存储与搜索 |
| `macro_research` | 指标定义、经济发布、FOMC、预测口径和研究业务验收 |
| `ai_documents` | 文档采集解析、检索/RAG、上下文快照、引用、Prompt 和 AI 评测 |
| `engineering` | Web、API、Worker、数据库、SDK 和跨栈代码实现 |
| `quality` | 独立测试策略、后端契约、前端/E2E、全栈回归和数据审计 |
| `security_compliance` | 认证授权、租户隔离、Web 安全、许可、秘密、依赖和云安全 |
| `operations` | 本地环境、容器、可观测性、部署、备份恢复和事件响应 |
| `integration_release` | 变更审查、冲突、契约同步、基线整合、发布门禁与回滚 |
| `knowledge` | ADR/开发文档规范、结论报告 Schema、任务索引和知识沉淀 |

强制触发器至少应有以下稳定 ID，校验器按 ID 检查覆盖：

| 触发器 ID | 条件 | 必须参与部门 |
| --- | --- | --- |
| `product_behavior` | 改变用户流程、需求边界或产品验收 | `product` |
| `public_contract` | 公共 API、OpenAPI、SDK、跨模块接口或数据库 Schema/迁移 | `architecture`, `integration_release` |
| `provider_ingestion` | 新增/修改 Provider、来源映射、解析或回填 | `data_sources`, `data_platform`, `engineering`, `quality` |
| `observation_semantics` | observation vintage、血缘、派生公式、发布批次或预测快照 | `data_platform`, `macro_research`, `quality`, `integration_release` |
| `research_definition` | 指标、发布、FOMC、预测或研究口径变化 | `macro_research`, `data_platform`, `quality` |
| `ai_or_documents` | 文档摄取/检索/RAG、AI 输出、Prompt、上下文、引用或评测 | `ai_documents`, `engineering`, `security_compliance`, `quality` |
| `user_or_untrusted_data` | 认证授权、工作区所有权、上传、非可信 HTML、许可或秘密 | `security_compliance`, `engineering`, `quality` |
| `implementation_change` | 修改可执行代码、构建配置、迁移或运行配置 | `engineering`, `quality`, `integration_release` |
| `production_change` | 部署、云资源、运行时配置、备份恢复或生产事件 | `operations`, `security_compliance`, `quality`, `integration_release` |
| `governance_or_knowledge` | 修改 AGENTS、组织合同、ADR、报告 Schema 或任务索引 | `architecture`, `knowledge`, `quality`, `integration_release` |

若一个任务命中多个触发器，取部门并集。无规则能确定 PRIMARY 时，来源主线程必须 `BLOCKED` 并请求用户或架构部先界定目标，不能任意指派研发部作为兜底。

### 3.7 每任务目录、部门报告与主总结

每个 substantive task 必须使用：

```text
docs/conclusions/tasks/<task-id>/
├── task-card.md
├── department-<department-code>-<seat-number>.md
└── summary.md
```

`task-card.md` 是分派账本，必须包含机器可读元数据：contract version、task ID、source title/ID、目标、成功标准、范围、依赖、检查、状态，以及每个 department assignment 的 role、department code、thread title/ID、accepted scope、report path、receipt status、receipt commit、result status。建议使用 YAML front matter，正文保留人类可读说明。

每个参与部门只能写自己的报告。部门报告必须包含：task ID、contract version、role、thread title/ID、receipt commit、actual scope、artifacts/commits、checks、evidence、risks、blockers、final status，以及根 `AGENTS.md` 要求的七个编号章节。允许状态为 `COMPLETE` 或 `BLOCKED`；若实现已完成但待集成，可在任务卡运行状态使用 `REVIEW`，报告最终事实仍应明确是否完成本部门责任。

`summary.md` 只能由来源主线程在所有必需部门报告存在后编写，必须包含：task ID、source title/ID、参与部门及报告路径、receipt commit、部门结果、集成提交、最终检查、未执行检查、风险/阻塞、final status，以及同样的七个编号章节。summary 的结论必须引用部门报告和 commit，不能替代缺失报告。任一必需报告缺失或 `BLOCKED` 时，summary 只能为 `BLOCKED`。

### 3.8 `.codex/organization.toml` 建议字段

建议把 `version` 升级为合同版本，并增加以下机器字段；字段名可以按实现语言微调，但语义和枚举不可弱化：

```toml
version = 2
project = "MacroLens"
operating_model = "independent_main_threads_with_shared_department_pool"

[coordination]
task_id_format = "^ML-[0-9]{8}-[0-9]{3}$"
seat_states = ["IDLE", "RESERVED", "RUNNING", "REVIEW", "BLOCKED"]
active_seat_states = ["RESERVED", "RUNNING", "REVIEW", "BLOCKED"]
one_active_task_per_seat = true
main_threads_are_peers = true
main_threads_may_implement = false
ambiguous_task_is_substantive = true
substantive_task_requires_assignment = true
primary_count = 1
supporting_min = 0
unmatched_route_status = "BLOCKED"
unavailable_seat_status = "BLOCKED"

[coordination.exemptions]
allowed = ["INITIALIZATION_ONLY", "RECEIPT_ONLY", "COORDINATION_ONLY", "RECORDED_STATUS_ONLY"]
may_modify_files = false
may_create_worktree = false
may_produce_domain_conclusion = false

[coordination.receipt]
required_before_work = true
allowed_roles = ["PRIMARY", "SUPPORTING"]
success_status = "RESERVED"
failure_status = "BLOCKED"
required_success_fields = ["status", "task_id", "role", "thread_title", "thread_id", "accepted_scope", "report_path"]
required_failure_fields = ["status", "task_id", "role", "thread_title", "thread_id", "reason"]
require_source_thread_identity_match = true
require_prework_evidence_commit = true
late_receipt_is_valid = false

[coordination.reporting]
task_root_pattern = "docs/conclusions/tasks/{task_id}"
task_card_filename = "task-card.md"
department_report_pattern = "department-{department_code}-{seat_number}.md"
summary_filename = "summary.md"
department_report_required = true
main_summary_required = true
required_conclusion_sections = 7
blocked_department_blocks_summary = true

[coordination.validation]
fail_closed = true
require_matching_contract_versions = true
require_unique_department_codes = true
require_declared_seat_count_match = true
require_routing_coverage = true
require_known_trigger_departments = true
require_receipt_commit_ancestor = true
require_report_identity_match = true
require_unique_report_paths = true

[[routing_rules]]
department = "architecture"
owns = ["module_boundaries", "public_interfaces", "schema", "data_flow", "technical_decisions"]

[[mandatory_triggers]]
id = "public_contract"
when = ["public_api", "openapi", "sdk", "cross_module_interface", "database_schema", "migration"]
requires = ["architecture", "integration_release"]
```

全部 11 个 `[[departments]]` 还应新增稳定的 `report_slug`，并保持 `code` 唯一。全部 11 个部门必须各有至少一条 `[[routing_rules]]`；上述 10 个 `[[mandatory_triggers]]` 必须完整落地，`requires` 只能引用存在的 department code。

### 3.9 校验器应执行的检查

`scripts/validate_organization.py` 至少应：

1. 用 Python 3.12 `tomllib` 解析 TOML；解析失败立即非零退出。
2. 校验 `version`、`project`、operating model、环境模式和 integration owner 等顶层字段。
3. 校验 `main_thread_count == len(main_threads)`，`department_seat_count == sum(departments.seats)`，标题、部门代码和 `report_slug` 唯一，integration owner 存在。
4. 校验 `[coordination]`、`exemptions`、`receipt`、`reporting`、`validation` 的上述硬值，尤其是 `main_threads_may_implement = false`、`primary_count = 1`、`fail_closed = true` 和 `late_receipt_is_valid = false`。
5. 校验 receipt 必填字段集合与允许角色/状态，不允许缺字段、未知字段替代必填字段或空字符串。
6. 校验 11 个部门都有路由规则，触发器 ID 唯一，所有 `requires` 引用已声明部门，强制触发器集合无缺失。
7. 校验 `AGENTS.md` 与 README 声明相同 `contract_version`，并包含硬门禁章节锚点；不尝试从散文推断规则值。
8. 遍历 `docs/conclusions/tasks/ML-*`：任务目录名、task ID 和 task-card 元数据一致；PRIMARY 恰好一个；参与身份、范围、回执、报告路径唯一且完整。
9. 对已开工/完成任务校验 `receipt_commit` 存在，并用 `git merge-base --is-ancestor` 确认它早于部门产物提交、实现提交和 summary 提交；无法证明时失败。
10. 校验每个参与部门的报告存在、身份与任务卡一致、包含七个章节和检查证据；summary 独立存在并引用全部部门报告。
11. 对 `BLOCKED` 部门禁止任务卡/summary 声称整体成功；对缺少报告、检查或 commit 的任务禁止状态为完成。
12. 汇总全部错误后统一非零退出，便于一次修复；不得在错误时自动改文件或补默认值。

推荐代表性负向用例：零 PRIMARY、两个 PRIMARY、回执 thread ID 不符、事后 receipt commit、未知 department code、触发器漏部门、重复 report path、缺部门报告、部门 `BLOCKED` 但 summary 成功、三个文件版本不一致。正向用例应包括纯架构分析任务和跨 API + AI + 安全 + 实现的混合任务。

### 3.10 推荐实施顺序与完成条件

1. 架构与知识管理报告先完成并由来源主线程记录。
2. 研发部在独立 worktree 中同时更新 TOML、`AGENTS.md`、README，新增校验器及正反测试夹具。
3. 运行组织校验、仓库校验和 `git diff --check`，提交单一清晰 commit。
4. 集成发布部审查合同版本、公共规则一致性并整合到 baseline。
5. 测试部只在 baseline 上独立执行正向、负向和回归验证。
6. 来源主线程收齐部门报告后写 `summary.md`；任何证据缺失则交付 `BLOCKED`，不得降级为“部分成功”。

完成标准：任务卡中一个 PRIMARY 和所有强制 SUPPORTING 均有先行真实回执；组织校验器能让所有正向样例通过、所有指定负向样例失败；三份规则版本一致；所有部门报告与主总结存在并可追溯到提交和检查证据。

## 4. 解决这个问题使用的 Agents、skills、tools 以及阅读的文档

### Agents

- 本任务仅由 `ML | 架构部 | 01` 执行设计。
- 未创建、联系或委派协作子 Agent；跨部门复核和实现由来源主线程依任务卡另行调度。

### Skills

- `gpt-plan`：用于提取 agent instructions 的目标、权限边界、工具/路由规则、验证与停止条件；该 skill 促使设计先列出关键变更，并将绝对规则限制在真正不变量上。

### Tools

- `exec_command`：以 UTF-8 读取规则、任务卡、现有校验器和历史结论，核对 Git 状态与基线提交。
- `rg`：检索当前仓库是否已有组织校验器、task-level 报告约定和相关关键字。
- `apply_patch`：仅创建本报告文件。

### 阅读文档

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `docs/conclusions/tasks/ML-20260803-001/task-card.md`
- `scripts/validate_repository.py`
- `docs/conclusions/2026-08-03-multithread-department-workspace-implementation.md`
- `C:/Users/liuwl/.codex/skills/gpt-plan/SKILL.md`

## 5. 本次执行值得沉淀的经验或者模式

1. 治理规则要把“默认路径”设计成安全路径：白名单豁免比枚举所有实质任务更可靠。
2. 分派合规至少包含四个维度：正确部门、真实线程身份、明确范围、发生在工作之前；缺一不可。
3. 聊天回执解决真实性，Git 祖先关系解决时序性，结构化任务卡解决机器可查性，三者不能互相替代。
4. PRIMARY 表示核心结果责任，不等于可以绕过触发器；强制协作部门应采用集合并集。
5. 主线程的价值是编排和验收。若允许其在资源不足时“临时帮忙”，fail-closed 合同会失去意义。
6. TOML 应保存稳定规则和 ID，不应复制大段自然语言；Markdown 应解释规则而不成为第二个可冲突的规范源。
7. 机器校验必须有负向用例。只验证当前正确文件会遗漏最关键的绕过路径。

## 6. 问题解决后反推的更好初始提示词

> 请为 MacroLens 设计并落地一套 fail-closed 的多部门任务执行合同。先读取根 `AGENTS.md`、`.codex/organization.toml` 和 `docs/organization/README.md`，把除“仅初始化、仅回执、仅协调、仅复述已记录状态”外的任务默认视为 substantive。每个 substantive task 在开工前必须创建完整任务卡，指派恰好一个 PRIMARY 和按触发器加入的 SUPPORTING，并由每个真实部门线程分别返回包含 task ID、role、thread title/ID、accepted scope、report path 的 `RESERVED` 回执。来源主线程必须先把回执记录提交到 Git，再允许开工；无法匹配部门、没有空闲席位、字段不完整或回执证据晚于工作时一律 `BLOCKED`，主线程不得接管或事后补造证据。请把机器规则放入 TOML，把硬门禁放入 AGENTS，把流程和示例放入 README；为 11 个部门定义路由和可叠加强制触发器；规定每任务目录、每部门报告和独立 summary；新增校验器及正反测试，验证版本、席位数、路由覆盖、回执、Git 时序、报告完整性和状态一致性。编码由研发部 worktree 完成，集成发布部整合，测试部在 baseline 独立验收，并按任务目录生成全部结论报告。

## 7. 当前场景更优方案及一次解决的提示词

更优方案是在上述合同之上，把 `task-card.md` 的机器元数据抽成受版本控制的 YAML front matter，并让 `scripts/validate_organization.py` 同时承担“静态组织合同校验”和“任务证据链校验”。这样不需要从 Markdown 表格猜字段，也不需要增加数据库或外部服务；Git 已经提供不可忽略的先后顺序。长期可在 CI 中先运行组织校验，再运行仓库与业务检查，使违规任务在合并前失败。

一次解决的提示词：

> 在 MacroLens 中一次性实现 organization contract v2，并用本任务做端到端样例。`.codex/organization.toml` 是唯一机器规范源；`AGENTS.md` 只放不可绕过的运行门禁；`docs/organization/README.md` 解释流程。采用默认 substantive + 封闭豁免白名单，要求恰好一个 PRIMARY、零个或多个 SUPPORTING、所有强制触发器部门取并集、各席位先真实回执、来源主线程先提交 receipt evidence，再发送开工指令。主线程仅能建卡、派单、记录、协调、验收和写 summary，不得执行部门工作或补造证据；无匹配/无空闲/证据不完整时立即 BLOCKED。使用 YAML front matter 结构化 task-card、department report 和 summary，并用 Git ancestor 校验回执提交早于工作提交。为全部 11 个部门建立路由，为公共契约、Provider、observation、研究、AI/文档、安全、实现、生产和治理建立可叠加强制触发器。新增 `scripts/validate_organization.py` 和正反夹具，检查配置 Schema、版本一致、容量、唯一性、路由覆盖、回执身份、时序、报告路径、七节报告和最终状态；最后运行组织校验、仓库校验与 `git diff --check`。只由研发部实现并提交，集成发布部整合，测试部在 baseline 独立验收，所有参与部门各写报告，主线程最后写独立 summary。

## 检查、证据与风险

### 已执行检查与证据

- 已完整读取任务卡和三份现行组织规则。
- 已确认当前基线为 `ab049e5`，工作开始前任务卡已记录本席位 `RESERVED / IN_PROGRESS`。
- 已检索仓库，确认当前不存在 `scripts/validate_organization.py`，因此本报告没有把尚未存在的校验器声称为已验证。
- 已阅读现有 `scripts/validate_repository.py`，确认 Python 环境已有 YAML 使用先例；建议的结构化 front matter 不会引入新的格式生态。
- 已执行 `git diff --check`，现有已跟踪差异无空白错误；另对本报告执行了路径、七节标题、身份标记和行尾空白检查。
- 本任务只改报告文件；未执行 `git add`、`git commit`、合并、推送、部署或 worktree 操作。

### 风险与约束

- Git ancestor 只能证明“记录提交早于产物提交”，不能独立证明聊天内容确由某个线程发送；真实性仍需来源主线程保留线程工具返回的 thread ID。两类证据应联合使用。
- 当前任务卡是 Markdown 表格，没有 YAML front matter。研发实现时需要选择兼容迁移或让校验器同时支持 v1 样例；不应静默忽略旧格式。
- 将 `BLOCKED` 视为 active seat state 会使阻塞席位继续被占用，这是防止重复派单的安全选择；只有来源主线程明确关闭/重派任务后才能释放。
- 强制触发器不能只靠关键词自动判定。任务卡应显式列出 `trigger_ids`，校验器检查相应部门集合，来源主线程对触发器选择负责。
- 报告中的字段名是建议合同。实现时可以调整命名，但不得降低本文定义的不变量、证据或停止条件。

### 未执行检查及原因

- 未运行任务卡要求的 `python -X utf8 scripts/validate_organization.py`：该文件尚不存在。
- 未运行完整仓库验证或业务测试：本席位交付仅为治理设计报告，不修改代码或产品行为。

### 阻塞项

- 架构设计无阻塞。
- 后续实现依赖知识管理部复核、来源主线程固化设计证据、研发部 worktree 实现、集成发布部整合与测试部 baseline 验收。
