# ML-20260803-001 知识管理部证据闭环审阅报告

## 报告元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 线程标题：`ML | 知识管理部 | 01`
- 线程 ID：`019fc533-c4bb-71a3-b963-d39218141521`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 实际范围：审阅任务卡、部门报告、主任务总结的结构与证据完整性，提出可执行、可交叉校验的文档合同；未修改治理文件或代码。
- 修改产物：`docs/conclusions/tasks/ML-20260803-001/department-knowledge-01.md`
- 席位状态：`REVIEW`
- 部门结果：`SUCCEEDED`

## 审阅结论

当前任务卡已具备任务 ID、来源主线程、目标、范围、成功标准、部门分工、依赖、检查和预期报告，足以启动设计审阅；但当前仓库合同还没有形成完整证据闭环。最关键的缺口是：任务卡中的 `Receipt=RESERVED` 只是主线程维护的登记值，不等于目标部门线程确实返回过回执。静态仓库校验最多证明“字段存在且互相一致”，不能单独证明“真实线程事件发生过”。

建议采用三层证据：目标线程返回的标准回执是原始事实，任务目录中的回执记录是可审计快照，任务卡部门表只是索引。主任务只有在原始线程证据可定位、回执快照存在、任务卡索引与二者一致时，才能声明“已分派”。部门报告和主任务总结沿用同一身份键与状态枚举，从而把分派、执行、交付、验收和最终收口连成一条可验证链。

## 建议合同

### 1. 目录与路径命名

每个实质性任务使用唯一目录：

```text
docs/conclusions/tasks/<task-id>/
├── task-card.md
├── receipts/
│   ├── department-<department-code>-<seat-nn>.md
│   └── ...
├── department-<department-code>-<seat-nn>.md
├── ...
└── summary.md
```

约束如下：

1. `<task-id>` 必须匹配 `.codex/organization.toml` 的 `ML-YYYYMMDD-NNN`。
2. `<department-code>` 必须来自组织配置中的部门 `code`，例如 `knowledge`、`architecture`、`engineering`。
3. `<seat-nn>` 固定为两位十进制编号，并且不得超过该部门的 `seats`。
4. 每个任务只能有一个 `task-card.md` 和一个 `summary.md`；每个参与席位只能有一个回执记录和一个部门报告。
5. 回执记录与部门报告的文件干必须相同，例如 `receipts/department-knowledge-01.md` 对应 `department-knowledge-01.md`。
6. `report_path` 必须是仓库相对路径，必须位于当前任务目录，禁止绝对路径和 `..` 路径逃逸。
7. 身份主键采用 `thread_id`。`thread_title` 是必须的人类可读字段，但不能替代线程 ID。标题应统一为组织约定的规范形式，例如 `ML｜知识管理部｜01`；当前任务卡使用半角 `|`，组织配置使用全角 `｜`，实施前应选定一种规范形式并回填，避免校验结果依赖视觉相似字符。

### 2. 标准派单请求与标准回执

派单请求至少携带：`task_id`、`source_thread_title`、`source_thread_id`、`role`、`target_thread_title`、`target_thread_id`、`task_card_path`、`task_card_revision`、`requested_scope`、`success_criteria`、`dependencies`、`required_checks` 和 `expected_report_path`。`task_card_revision` 应为派单时可读取的 Git commit SHA；未提交时不得正式派单，因为目标线程无法稳定确认自己接受的是哪一版合同。

目标部门线程只允许返回以下两类机器可解析回执。接受时：

```text
status=RESERVED
task_id=ML-YYYYMMDD-NNN
role=PRIMARY|SUPPORTING
thread_title=<canonical department thread title>
thread_id=<target thread id>
source_thread_id=<source main thread id>
task_card_path=docs/conclusions/tasks/<task-id>/task-card.md
task_card_revision=<40-hex commit sha>
accepted_scope=<non-empty, bounded scope>
report_path=docs/conclusions/tasks/<task-id>/department-<department-code>-<seat-nn>.md
```

拒绝或无法接受时：

```text
status=BLOCKED
task_id=ML-YYYYMMDD-NNN
role=PRIMARY|SUPPORTING
thread_title=<canonical department thread title>
thread_id=<target thread id>
source_thread_id=<source main thread id>
task_card_path=docs/conclusions/tasks/<task-id>/task-card.md
task_card_revision=<40-hex commit sha or UNKNOWN>
accepted_scope=NONE
report_path=NONE
blocker_code=MISSING_TASK_FIELD|SEAT_NOT_IDLE|SCOPE_MISMATCH|DEPENDENCY_UNMET|NO_AVAILABLE_SEAT|OTHER
blocker_detail=<non-empty reason>
```

字段顺序固定；未知值不得用空字符串代替，必须使用合同允许的显式值。只有目标 `thread_id` 对应的真实线程返回的 `RESERVED` 才表示接受。主线程转述、任务卡手填、后补报告或同名线程回复都不能替代该回执。

### 3. 回执证据记录

主线程收到回执后，应原样保存到 `receipts/department-<department-code>-<seat-nn>.md`。回执记录除逐字回执块外，还必须包含：

- `task_id`
- `source_thread_id`
- `target_thread_id`
- `dispatch_evidence_ref`
- `receipt_evidence_ref`
- `observed_at`（带时区的 ISO 8601 时间）
- `receipt_sha256`（对规范化原始回执块计算）
- `recorded_by_thread_id`
- `task_card_revision`

`dispatch_evidence_ref` 和 `receipt_evidence_ref` 应优先使用线程系统返回的不可变消息 ID、事件 ID 或 cursor；如果工具只提供线程级定位，则至少记录目标线程 ID、可复查时间和回执摘要，并把证据等级标记为 `THREAD_LOCATOR_ONLY`。静态 validator 可以验证字段、摘要、路径及跨文件一致性；在线验收必须重新读取目标线程历史，确认该线程确实返回了摘要匹配的回执。没有可复查的线程证据时，证据等级只能是 `UNVERIFIED`，主任务不得进入 `READY` 或声称“已分派”。

这条规则用于直接防止主任务只在任务卡里填写 `RESERVED`：任务卡是索引，不是原始证据；回执快照是审计材料，但也不是身份事实；目标线程历史才是派单真实性来源。

### 4. 任务卡必须字段

任务卡必须包含以下结构：

- 注册：任务 ID、来源主线程标题/ID、任务类型、创建时间、当前主任务状态、任务卡 revision。
- 问题与目标：业务场景、目标、范围内、范围外。
- 验收：逐条编号的成功标准、必须执行的检查、允许跳过检查的授权主体与记录方式。
- 路由：恰好一个 `PRIMARY`、零个或多个 `SUPPORTING`、每个席位的标题/ID、部门 code、请求范围、预期报告、回执状态、结果状态、证据记录路径。
- 依赖：任务级依赖、部门执行顺序、阻塞时的责任人和恢复条件。
- 变更控制：工作树、起始提交、允许修改的模块、公共接口或 Schema 影响、提交/集成责任。
- 收口：部门报告集合、主总结路径、最终检查、最终状态和完成时间。

部门表应至少增加 `Department code`、`Receipt evidence` 和 `Task-card revision`，并将当前混用的状态拆开。`Receipt` 只使用 `PENDING|RESERVED|BLOCKED`；`Result` 只使用 `PENDING|RUNNING|SUCCEEDED|FAILED|BLOCKED`。

### 5. 部门报告必须字段

每份 `department-*.md` 必须包含：

- 身份：任务 ID、角色、部门 code、线程标题/ID、来源主线程标题/ID。
- 合同：接受的任务卡 revision、接受范围、明确的范围外、回执证据路径。
- 执行：实际范围、工作流程、产物路径、提交 SHA；不涉及提交时显式写 `N/A` 及原因。
- 校验：每条必需检查的命令、结果、时间或关联证据；未运行的检查、原因和授权人。
- 证据：输入文档、代码位置、工具输出、外部证据定位；结论必须能回指证据。
- 风险：已知风险、兼容性、遗留项、阻塞项和解除条件。
- 结果：`SUCCEEDED|FAILED|BLOCKED`，完成时间；不得使用含糊的“完成”描述代替枚举。
- 交接：给来源主线程或集成发布部的明确说明。
- 根 `AGENTS.md` 要求的七个总结章节，章节名称或稳定编号必须可被 validator 识别。

部门报告的 `SUCCEEDED` 只代表该席位接受范围已完成，不自动代表主任务成功。部门不得把范围外工作写成已完成，也不得用另一个线程的检查结果冒充本席位已执行检查。

### 6. 主任务总结必须字段

`summary.md` 必须与部门报告分离，并包含：

- 任务 ID、来源主线程标题/ID、任务卡路径与最终 revision。
- 原始目标、实际范围、范围变更及其批准证据。
- 路由决定：为什么某部门是 PRIMARY、为什么选择每个 SUPPORTING、哪些强制触发规则被应用。
- 全部参与席位清单：角色、线程 ID、回执证据路径、部门报告路径、结果和提交 SHA。
- 成功标准逐条对照表：每条标准必须指向具体产物、检查输出、部门报告或提交。
- 必需检查及结果；跳过项必须有授权、风险和后续责任人。
- 集成证据：集成提交、基线、冲突处理和集成发布部结论；无代码任务写 `N/A`。
- 风险、阻塞、失败项、未完成项和后续任务 ID。
- 最终状态：`SUCCEEDED|FAILED|BLOCKED`，以及符合下述收口规则的理由。
- 根 `AGENTS.md` 要求的七个总结章节。

主总结不能把任务卡表中的 `RESERVED` 直接解释为实际分派证据，也不能把报告文件“存在”直接解释为部门成功。它必须逐项引用回执证据和部门报告中的终态。

### 7. 状态机与收口规则

应分别管理四类状态，禁止跨层复用：

| 层级 | 允许状态 | 说明 |
| --- | --- | --- |
| 席位 | `IDLE`, `RESERVED`, `RUNNING`, `REVIEW`, `BLOCKED` | 组织配置中的资源占用状态 |
| 回执 | `PENDING`, `RESERVED`, `BLOCKED` | 一次派单是否被目标线程接受 |
| 部门结果 | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `BLOCKED` | 单个席位交付结果 |
| 主任务 | `DRAFT`, `DISPATCHING`, `READY`, `RUNNING`, `REVIEW`, `SUCCEEDED`, `FAILED`, `BLOCKED` | 全任务生命周期 |

主任务的合法转换为：

```text
DRAFT -> DISPATCHING
DISPATCHING -> READY | BLOCKED
READY -> RUNNING
RUNNING -> REVIEW | FAILED | BLOCKED
REVIEW -> SUCCEEDED | FAILED | BLOCKED
BLOCKED -> DISPATCHING | RUNNING
```

`SUCCEEDED` 和 `FAILED` 是终态；若终态后改变目标或修复失败，应创建新任务 ID，或采用明确、可审计的 reopen 版本规则，不能静默改写历史。

关键门禁：

1. `DRAFT -> DISPATCHING`：任务卡必填字段完整且 revision 已固定。
2. `DISPATCHING -> READY`：恰好一个 PRIMARY 和所有强制 SUPPORTING 均有匹配目标线程 ID 的 `RESERVED` 原始证据；所有回执接受同一 task-card revision。
3. 任一必需席位无匹配、无空闲席位、拒绝接单或证据不可验证：主任务进入 `BLOCKED`，主线程不得代做、不得把可选部门伪装成已接受。
4. `READY -> RUNNING`：依赖满足，来源主线程显式发出开工指令；部门结果从 `PENDING` 进入 `RUNNING`，席位从 `RESERVED` 进入 `RUNNING`。
5. `RUNNING -> REVIEW`：所有必需部门都已提交结构完整的终态报告；实现提交已由集成发布部处理，或明确为无代码任务。
6. `REVIEW -> SUCCEEDED`：所有成功标准都有证据、所有必需部门结果为 `SUCCEEDED`、必需检查通过或有合规豁免、回执与报告交叉一致、`summary.md` 已生成且 validator 通过。
7. `REVIEW/RUNNING -> FAILED`：必需检查失败且不允许豁免、强制部门结论为 `FAILED`、产物不满足成功标准，或证据存在不可调和的身份/版本冲突。即使失败，也必须生成部门报告和主总结。
8. `* -> BLOCKED`：缺少席位、权限、用户决策、外部依赖或可复查证据，且存在明确恢复条件。阻塞记录必须包含 `blocker_code`、责任人、解除条件和最后检查时间；`BLOCKED` 不是成功，也不能作为无报告退出。
9. 席位只有在来源主线程确认报告已接收、实现已集成或明确无需集成后，才能从 `REVIEW` 返回 `IDLE`。接单前拒绝时，目标席位保持 `IDLE`；执行中受阻时才进入席位 `BLOCKED`。

当前任务卡把部门结果写成 `IN_PROGRESS`，而组织席位状态使用 `RUNNING`。建议按上表统一为部门结果 `RUNNING`，否则 validator 和人工审阅会对同一阶段产生两种解释。

### 8. 机器校验最小集合

组织合同 validator 至少应验证：

1. 任务 ID、目录名和任务卡字段一致。
2. 恰好一个 PRIMARY；所有部门 code、席位号和线程 ID 非空且不重复。
3. 报告路径、回执路径符合当前任务目录命名规则，且不存在路径逃逸。
4. 每个 `RESERVED` 都有回执记录；回执的任务 ID、角色、线程 ID、任务卡 revision、范围和报告路径与任务卡一致。
5. `receipt_sha256` 能由保存的原始回执块重算；证据引用与证据等级存在。
6. 每个部门终态都有对应报告，报告身份与任务卡一致，且包含七个总结章节。
7. `summary.md` 引用的席位集合、报告、结果和提交与任务卡、回执记录、部门报告一致。
8. 主任务 `SUCCEEDED` 时，所有强制报告为 `SUCCEEDED`、必需检查有通过证据、没有未解决 `BLOCKED/FAILED/PENDING/RUNNING`。
9. 主任务 `FAILED` 或 `BLOCKED` 时仍存在 `summary.md`，并具有原因、责任人或恢复/后续条件。
10. 标题规范、状态枚举和时间格式唯一，不接受视觉相似分隔符或未声明状态。

validator 必须清楚输出自己的证明边界：`STATIC_CONSISTENT` 只表示仓库文件自洽；只有结合线程历史复查后才可输出 `THREAD_EVIDENCE_VERIFIED`。将静态自洽标成“已真实分派”会产生虚假确定性。

## 检查与证据

- 已完整读取：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260803-001/task-card.md`。
- 已核对提交：`ab049e5`（`docs: record governance design receipts`），确认该提交把架构部和知识管理部的任务卡登记更新为 `RESERVED / IN_PROGRESS`。
- 已核对任务目录：审阅开始时只有 `task-card.md`，尚无独立回执证据文件、部门报告或主总结。
- 已核对工作区：写入本报告前 `git status --short` 无输出。
- 已核对 validator：任务卡要求的 `scripts/validate_organization.py` 当前不存在；`scripts/validate_repository.py` 存在，但并不验证任务卡、回执、部门报告或主总结合同。
- 本报告不声称验证了其他部门的真实线程回执；`ab049e5` 和任务卡表仅证明主线程记录了该状态，不能证明原始线程事件。
- 已执行 `python -X utf8 scripts/validate_repository.py`：通过，输出 `Repository contract valid: 61 source series, 62 API paths`。
- 已执行 `git diff --check`：当前已跟踪差异通过，无输出；本报告是未跟踪文件，不在该命令的检查集合内，因此另以逐行尾随空白检查验证 295 行均无行尾空格或制表符。
- 已执行报告结构标记检查：通过，任务/线程身份、建议合同、检查/证据、风险和七个总结章节共 12 个必需标记全部存在。
- 未执行 `python -X utf8 scripts/validate_organization.py`：脚本当前不存在，这是来源任务后续实现范围，不是本席位可修改范围。

## 风险与遗留项

1. 如果实现只校验 Markdown 中的字段存在，主线程仍可事后构造全套自洽文件，因此必须保留在线线程证据复核边界。
2. 若线程工具不提供消息 ID 或事件 ID，只能达到线程定位加内容摘要的较弱证明；应在总结中显式标注证据等级，不得冒充强证明。
3. 当前任务卡没有独立回执记录路径和 task-card revision 列，后续实现需要补齐，否则部门可能接受不同版本的任务卡。
4. 半角/全角竖线标题混用会导致严格字符串校验失败或宽松校验误匹配；身份必须以 thread ID 为主，并统一规范标题。
5. `IN_PROGRESS`、`RUNNING`、`REVIEW` 同时存在但含义未拆分，容易把席位占用状态误当作交付结果。
6. `scripts/validate_organization.py` 尚未存在，本报告只能定义合同，不能证明未来实现满足合同。
7. 如果允许跳过检查却不记录授权主体、理由和风险，主任务可能以“未执行但无影响”绕过失败收口。

## 1. 本次遇到的问题以及场景

MacroLens 正在把“先分派到正确部门、部门留存结果、主任务基于证据总结”固化为仓库治理合同。本次场景不是实现代码，而是从知识管理角度审阅任务卡、部门报告和主任务总结能否形成证据闭环。现有文档已经规定任务卡和部门交付格式，但没有把真实线程回执、仓库登记和最终声明分成不同证据层，也没有统一任务、席位、回执和部门结果的状态。

## 2. 分析这个问题的过程

先读取根工程规则、组织配置、组织手册和当前任务卡，确认任务卡具备启动审阅所需字段。随后核对 `ab049e5`、任务目录、工作区和现有 validator，比较“仓库里写了什么”与“这些文件实际能证明什么”。分析发现，任务卡可以证明主线程登记了回执状态，但无法独立证明目标线程确实接受；同时，标题分隔符和运行状态存在不一致。基于这些事实，将合同拆成身份、派单、回执证据、部门交付、主任务汇总和状态收口六个互相引用的层次。

## 3. 解决这个问题的工作流程

1. 固定任务卡 revision 后再派单。
2. 目标部门线程以固定字段返回 `RESERVED` 或 `BLOCKED`。
3. 主线程保存逐字回执、线程证据定位和内容摘要，任务卡只登记索引。
4. 所有必需部门回执通过身份与版本检查后，主任务才能进入 `READY`。
5. 部门按唯一报告路径交付实际范围、产物、检查、证据、风险和终态。
6. 主线程逐条映射成功标准到部门报告和产物，不以文件存在代替成功。
7. 静态 validator 检查目录、字段、枚举、摘要和跨文件一致性；在线检查复核真实线程历史。
8. 按成功、失败或阻塞规则生成独立 `summary.md`，任何结果都不允许无报告退出。

## 4. 使用的 Agents、skills、tools 以及阅读文档

### Agents / 线程

- 执行席位：`ML | 知识管理部 | 01`。
- 角色：`SUPPORTING`。
- 未创建、联系或委派其他 Agent；全部审阅由本席位完成。

### Skills

- 未使用专项 skill。本任务是仓库内组织文档合同审阅，当前可用 skills 中没有比直接依据项目规则审阅更匹配的强制流程。

### Tools

- `exec_command`：只读加载规则与任务卡、检查任务目录、Git 状态、提交和 validator 文件。
- `apply_patch`：仅创建本部门独占报告文件。

### 阅读文档

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `docs/conclusions/tasks/ML-20260803-001/task-card.md`
- `docs/conclusions/2026-08-03-multithread-department-workspace-implementation.md`（用于核对既有七章报告惯例）
- `scripts/validate_repository.py`（用于确认现有校验范围）

## 5. 值得沉淀的经验或者模式

1. 登记不是证据：任务卡状态是索引，原始线程事件才是分派真实性来源。
2. 静态校验和在线校验必须明确分层；前者验证自洽，后者验证事件确实来自目标线程。
3. 身份、资源占用、接受状态和交付结果要使用不同字段与枚举，避免一个 `status` 承担四种语义。
4. 所有参与者必须接受同一个任务卡 revision，否则“都已同意”可能只是接受了不同版本。
5. 成功、失败和阻塞都需要结构化收口；失败或阻塞不是跳过报告的理由。
6. 路径规则本身是合同的一部分。稳定、可推导的命名让 validator 能发现漏报、重报和错配。
7. 内容摘要可以发现回执快照被修改，但不能证明作者身份；必须结合线程系统提供的事件定位。

## 6. 反推一条更好的初始提示词

> 请为 MacroLens 设计并落地一套可审计的多线程任务证据合同。先读取仓库组织规则和当前任务卡，明确区分席位状态、派单回执、部门结果和主任务状态。要求主任务在开工前固定任务卡 commit revision，向一个 PRIMARY 和所有强制 SUPPORTING 的真实线程派单，并保存目标线程返回的标准回执、线程事件定位和回执摘要；任务卡只作为索引，不能作为派单真实性证据。统一 `docs/conclusions/tasks/<task-id>/` 下的 task-card、receipts、department reports 和 summary 路径及字段；定义成功、失败、阻塞的终态规则。实现静态 validator 检查跨文件一致性，并明确它不能替代在线线程历史验证。使用当前任务做端到端样例，运行组织校验、仓库校验和 `git diff --check`。

## 7. 当前场景是否有更优方案及一次解决的提示词

更优方案是把证据闭环实现为“双验证器”：仓库内 validator 负责可复现的静态合同，来源主线程在最终收口前调用线程读取能力完成在线真实性验证，并把验证时间、目标线程 ID、事件定位和回执摘要写入总结。这样既避免把易变的聊天全文塞入仓库，也不会把主线程自行维护的 Markdown 当成不可伪造证据。若未来线程平台提供签名事件或不可变导出，可直接升级 `evidence_ref`，而不必改变任务卡和报告主结构。

对应的一次解决提示词：

> 请一次性实现 MacroLens 的“静态合同 + 在线线程证明”任务治理：以 thread ID 为身份主键，以已提交的 task-card revision 为派单版本；部门必须从目标线程返回固定格式 `RESERVED/BLOCKED` 回执。主线程保存逐字回执、事件引用、时间和 SHA-256，并且只有在线重读目标线程验证摘要后才能标记为已分派。为任务卡、回执记录、部门报告和 summary 定义固定路径、必填字段与四层状态机；恰好一个 PRIMARY，强制支持部门缺席或无席位立即 BLOCKED，主线程不得代做。实现 validator 检查目录、字段、状态、版本、摘要和跨文件一致性，并在输出中区分 `STATIC_CONSISTENT` 与 `THREAD_EVIDENCE_VERIFIED`。最后用一个成功样例和缺回执、错线程、错 revision、失败检查、无可用席位五个反例验收。
