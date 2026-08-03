# ML-20260803-001 集成发布部 01 报告

## 报告元数据

- Contract version：`1`（当前 main 尚未集成候选 v2）
- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 接受的任务卡 revision：`3ce8ff8`
- 回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01.md`
- 审查基线：`8c52c631adf1cbc9d430a419571929baf6fce533`
- 研发候选提交：`d1e5b40804805e67681893af63cffd83fd0000e5`
- 集成方式：候选提交未 cherry-pick；审查门禁 fail closed
- 集成提交：`N/A`
- Git 冲突：未进入 cherry-pick，因此无 Git 冲突
- 合同冲突：存在，详见“审查结论”
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

## 首次审查结论（轮次 01，保留历史）

研发提交的文件范围符合任务卡，只修改或新增以下 6 个授权文件：

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `scripts/validate_organization.py`
- `scripts/test_validate_organization.py`
- `docs/conclusions/tasks/ML-20260803-001/department-engineering-04.md`

候选 diff 的空白检查通过，Python 3.12 类型风格与安全规则没有新增违规，静态校验和在线线程
证明的边界文案也正确。但审查发现以下集成级阻塞，因此未把候选提交写入 `main`：

1. `scripts/validate_organization.py` 只检查成功回执必填字段的子集，漏掉
   `source_thread_id`、`task_card_path`，并且完全没有检查 `required_failure_fields`。删除或篡改
   这些声明后仍可能输出 `STATIC_CONSISTENT`，与完整回执和缺失即 `BLOCKED` 的硬门禁冲突。
2. `.codex/organization.toml` 的报告路径模板使用 `{department_code}`，但多词部门另定义了连字符
   `report_slug` 且 validator 不消费该字段。对本席位会推导出
   `department-integration_release-01.md`，与任务卡、已固化回执和本报告要求的
   `department-integration-release-01.md` 冲突。
3. TOML 声明 `require_receipt_commit_ancestor`、`require_report_identity_match` 和
   `require_unique_report_paths` 为强制校验，但 validator 只验证这些开关值为 `true`，没有执行
   对应任务证据检查。它也不遍历任务目录校验 PRIMARY、回执 revision、部门报告、summary 与
   状态一致性。因此当前实现无法支撑任务卡成功标准 5、6 的完整机器门禁。
4. 针对性测试只覆盖当前合同正例、文档版本漂移、未知触发部门和主线程实现门禁，未覆盖上述
   假阴性与路径冲突。

## 首次检查、风险与恢复条件（轮次 01，保留历史）

### 已执行检查

- `git status --short`：审查开始前无输出，工作区干净。
- `git branch --show-current`：`main`。
- `git rev-parse HEAD`：`8c52c631adf1cbc9d430a419571929baf6fce533`。
- `git diff --check d1e5b40^ d1e5b40`：通过，无输出。
- `python -X utf8 scripts/validate_repository.py`：通过，Python `3.11.9`，输出
  `Repository contract valid: 61 source series, 62 API paths`。
- `git diff --check`：通过，无输出。
- 已确认优先解释器 `py -3.12` 为 Python `3.12.9`；PATH 中 `python` 为 Python `3.11.9`。

### 未通过或未执行检查

- `python -X utf8 scripts/validate_organization.py`：退出码 `2`；当前 main 未集成候选提交，脚本
  不存在。
- `python -X utf8 scripts/test_validate_organization.py`：退出码 `2`；同上。
- 未在 main 上执行候选组织校验和针对性测试，因为把已知违反合同的提交写入基线会绕过集成
  门禁；本报告不把研发部门在其 worktree 中的结果冒充为本席位检查结果。
- 未执行后端和 Web 全量门禁；候选未进入基线，且任务卡本轮指定的是组织、仓库与 diff 检查。

### 风险与恢复条件

- 若直接集成，机器校验可能对缺失回执字段或缺失任务证据给出错误的静态一致结论。
- 报告路径规则会使任务卡、回执、报告与机器模板对多词部门产生不一致。
- 恢复条件：研发部提交后续修正，至少统一 `department_code/report_slug` 的路径语义，补齐全部
  必填回执字段校验，并让实现与 TOML 声明的证据门禁一致；增加能证明上述缺陷被拒绝的负向
  测试。来源主线程随后重新派发集成审查。

## 集成复审轮次 02

### 复审元数据

- 复审角色：`SUPPORTING（集成复审轮次 02）`
- 接受的任务卡 revision：`c4a73be`
- 复审回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-review-02.md`
- 复审开始 main：`81e428776dedbf9c4fe7d6a398180dcb08c74027`
- 候选分支：`codex/ml-20260803-001-engineering-04`
- 候选 tip：`c9353fd1ed639bd84f0668dd57c50283435b65f7`
- 固定审查点：`cba3be3cdc5f3d2587d5d085d080652b0b14e8df`
- 候选提交序列：`d1e5b40`、`0e353ac`、`c9353fd`
- 集成方式：未 merge；复审硬门禁失败，按 fail closed 保留 main 证据历史
- 集成 commit：`N/A`
- 报告更新 commit：本文件最终提交无法自引用，准确 SHA 记录在本席位交付回复
- Git 冲突：未进入 merge，因此无 Git 冲突
- 证据兼容冲突：候选不接受本轮已固化的 `-review-02` 回执文件与轮次化 role
- 复审最终状态：`BLOCKED`

### 首次 4 类阻塞逐项核验

| 首次阻塞 | 复审状态 | 证据 |
| --- | --- | --- |
| 成功/失败回执字段假阴性 | **未修复** | TOML 声明集合已改为精确相等校验，但实际回执解析仍只强制 `status/task_id/role/thread_id/report_path/thread_title`；`source_thread_id`、`task_card_path`、`task_card_revision` 仍是“存在才校验”，完全漏查 `accepted_scope`。`BLOCKED` 回执不强制 `reason`，反而错误要求 `report_path`。 |
| 多词部门路径冲突 | **已修复** | 三份规则和 validator 统一使用唯一 `{report_slug}`；`integration_release -> integration-release` 映射被强制校验，错误下划线 slug 有负例。 |
| 任务证据门禁只验开关 | **部分修复，仍阻塞** | 已实现任务目录遍历、单一 PRIMARY、路径唯一、部分 receipt/report/summary 检查；但 revision 未绑定到“该 SHA 实际包含任务卡”，整改回执提交未用于整改报告/提交时序，报告身份漏 title/source/revision/scope，summary 漏七章、来源身份、报告引用、checks/evidence/risks。 |
| 负向测试不足 | **未修复** | 测试总数为 17，其中 2 个正例、15 个负例，不是本轮要求的 17 个负例；缺少实际成功回执缺字段、失败 `reason`、task-card revision 实体绑定、整改时序、完整 report/summary identity 等绕过用例。 |

### 新发现的基线兼容阻塞

1. main 在复审派单后新增并固化
   `receipts/department-integration-release-01-review-02.md`。候选 `_receipt_filename_pattern()`
   只允许标准回执或 `-remediation-NN`，对该文件返回不匹配；合并后 validator 会直接报回执文件名
   违反合同。
2. 本轮逐字回执的 role 是 `SUPPORTING（集成复审轮次 02）`，而任务卡 assignment role 和候选
   枚举是 `SUPPORTING`。候选按精确相等校验会失败。集成不得删除、改写或忽略 main 已固化证据，
   因而不能用冲突处理掩盖该不兼容。
3. 用户指定的直接命令 `py -3.12 -X utf8 scripts/test_validate_organization.py` 在候选 worktree
   退出 `1`，报 `ModuleNotFoundError: No module named 'scripts'`。只有改用
   `-m unittest scripts.test_validate_organization` 才能运行 17 项测试，未满足本轮原样门禁。

### 复审轮次 02 检查

- 候选 worktree `HEAD`：`c9353fd1ed639bd84f0668dd57c50283435b65f7`，检查前后
  `git status --short` 无输出。
- `py -3.12 --version`：`Python 3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：候选自洽样本通过，输出
  `STATIC_CONSISTENT: MacroLens organization contract v2`；该分支尚不包含 main 的复审回执。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：失败，退出码 `1`，直接运行时无法导入
  `scripts`。
- `py -3.12 -X utf8 -m unittest scripts.test_validate_organization`：通过，`Ran 17 tests`；静态
  计数为 2 个正例、15 个负例。
- `py -3.12 -X utf8 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：
  通过；字节码目录定向到系统临时目录，未污染候选 worktree。
- `py -3.12 -X utf8 scripts/validate_repository.py`：首次失败，退出码 `1`，Python 3.12 环境缺少
  `yaml`。仅为该进程临时设置 Python 3.11 site-packages 的 `PYTHONPATH` 后通过，输出
  `Repository contract valid: 61 source series, 62 API paths`；未安装或修改全局依赖。
- 候选 worktree `git diff --check`：通过，无输出。
- 根 main 未合入候选，因此没有把候选自测结果表述为 main 集成门禁通过。

### 复审风险与恢复条件

- 直接 merge 会让 main 上已固化的复审回执触发 validator 失败，同时继续允许不完整成功/失败
  回执和不完整 summary 通过，既不能静态自洽，也不能满足任务卡成功标准 2、5、6。
- 恢复条件：研发部必须让实际 Raw receipt 校验严格区分成功/失败字段；把 revision 与真实任务卡
  内容、各轮 receipt 与对应产物/提交时序绑定；补齐 report/summary 合同；定义并验证复审回执
  的路径与基础 role/轮次元数据语义；使用户指定的直接测试命令可运行；补足至少 17 个负例。
- 修正后应重新基于最新 main 证据同步候选分支，再派发下一轮集成复审。

## 1. 本次遇到的问题以及场景

本席位负责把研发治理合同提交集成到 `main`，同时守住变更范围、合同同步和发布门禁。候选提交
表面上通过研发侧静态校验，但完整 diff 审查发现 validator 的实际证明能力弱于 TOML 和文档声明，
并且多词部门报告路径与当前任务证据发生冲突。若继续 cherry-pick，`main` 会得到一个能够对部分
不合规状态输出 `STATIC_CONSISTENT` 的合同，因此按 fail-closed 规则停止集成。

复审轮次 02 面对的是同一候选经 `c9353fd` 整改后的重新集成。虽然 slug、任务目录遍历和单一
PRIMARY 已修复，但完整回执、Git 时序、报告/summary 合同和负例仍不完整；最新 main 的复审回执
也不在候选支持的证据生命周期中。因此本轮再次停止集成。

## 2. 分析这个问题的过程

先核对指定工作目录、`main`、干净状态和精确 HEAD，再确认研发基线是当前 main 的祖先，候选只
触及 6 个授权文件。随后完整读取任务卡、架构部、知识管理部和研发部报告，逐文件阅读候选 diff，
并把审查拆成规范轴和规格轴。规范轴将实现与根规则、TOML 和组织手册对照；规格轴将实现与任务卡
成功标准以及架构/知识设计逐条对照。两个轴独立得到相同核心结论：validator 存在可复现的声明与
实现落差，且路径合同未同步。

复审时将固定点更新为 `cba3be3...c9353fd`，重新并行执行 Standards/Spec 两轴，再由主席位完整
阅读整改后的 1095 行 validator、301 行测试、TOML、三份规则 diff 和研发报告。随后用候选正则
验证最新 main 回执的路径兼容性，并分别运行用户指定的直接脚本命令和研发使用的 unittest 模块
命令，确认两者结果不同。

## 3. 解决这个问题的工作流程

1. 固定基线 `8c52c63` 和候选 `d1e5b40`，验证工作区与提交关系。
2. 核对候选变更文件集合，确认没有产品、API、Schema 或部署范围扩张。
3. 完整读取任务卡、三份部门报告和候选六文件 diff。
4. 分别执行 Standards 与 Spec 审查，汇总硬违规和判断项。
5. 运行当前基线可执行的仓库检查、工作区 diff 检查与候选 diff 空白检查，并记录 Python 版本。
6. 因硬门禁失败而不执行 cherry-pick，只写本席位独占报告并提交，保留 main 的可恢复干净状态。
7. 将修正范围和重新集成条件交还来源主线程调度，不代研发部修复，也不代测试部下结论。

复审轮次 02 新增四项门禁：逐条回归首次阻塞、静态计算正/负测试数量、核对候选与最新 main
证据文件的 merge 后兼容性、原样运行用户指定的 Python 3.12 命令。任一硬缺陷存在即不进入
merge，保留 `81e4287` 之后仅增加本部门报告提交。

## 4. 使用的 Agents、skills、tools 以及阅读文档

### Agents

- 主执行席位：`ML｜集成发布部｜席位｜01`。
- `standards_review` 子 Agent：只读检查仓库规范、组织硬门禁和 Fowler smell。
- `spec_review` 子 Agent：只读核对任务卡成功标准与架构/知识设计。
- `standards_re_review` 子 Agent：复审整改后的规范符合性和首次阻塞回归。
- `spec_re_review` 子 Agent：复审任务规格、最新 main 证据兼容性与负例要求。

### Skills

- `code-review`：要求把规范符合性与规格符合性分轴独立审查。该流程直接暴露了 validator 假阴性
  和报告路径合同冲突；复审又独立确认整改仍不完整，因而两次触发集成暂停。

### Tools

- `exec_command`：读取 Git、文档和候选文件，核对提交关系、版本及运行门禁。
- `apply_patch`：只创建和更新本集成发布部报告。
- `update_plan`：维护核验、审查、集成判断、检查、报告与最终复核状态。
- collaboration Agent tools：按 `code-review` skill 并行执行两个只读审查轴。

### 阅读文档

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `docs/conclusions/tasks/ML-20260803-001/task-card.md`
- `docs/conclusions/tasks/ML-20260803-001/department-architecture-01.md`
- `docs/conclusions/tasks/ML-20260803-001/department-knowledge-01.md`
- 候选提交中的 `docs/conclusions/tasks/ML-20260803-001/department-engineering-04.md`
- `C:/Users/liuwl/.codex/skills/code-review/SKILL.md`
- 候选提交中全部 6 个变更文件及完整 diff
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-review-02.md`
- 候选提交 `c9353fd1ed639bd84f0668dd57c50283435b65f7` 中整改后的全部 6 个文件

## 5. 本次执行值得沉淀的经验或者模式

1. 校验器声明的门禁必须有实际执行路径，不能只验证“开关写成 true”。
2. 新增机器字段必须有唯一消费者；`report_slug` 与 `department_code` 并存但语义未贯通会制造
   视觉上不明显、机器上必然冲突的路径。
3. 正例通过只证明当前样本自洽；治理校验器必须用删除必填字段、错 revision、错路径、缺报告和
   错状态等负例证明 fail closed。
4. 集成部门应在写入基线前完成规格审查。可通过的测试不能覆盖已知规格缺口。
5. 静态一致性与真实线程身份是两种证明；明确边界是正确的，但静态一致性本身也必须完整实现。
6. 多轮任务应把基础角色和轮次类型拆成不同字段；把轮次文字拼入 role 会破坏枚举合同。
7. 负例数量和测试总数不能混用；门禁要求 17 个负例时，2 正 + 15 负不等于达标。
8. CLI 入口本身是合同。模块命令通过不能替代用户指定的直接脚本命令通过。

## 6. 问题解决后反推的一条更好初始提示词

> 请实现 MacroLens organization contract v2，并在交付前证明 validator 不会产生假阴性。完整
> 读取任务卡、架构与知识报告；统一 `department_code` 和文件 `report_slug` 的唯一语义，使多词
> 部门的 task-card、receipt、report 与模板一致。validator 必须校验成功/失败回执的全部必填字段、
> 四类状态枚举、全部 reporting/validation 硬门禁，并实际遍历任务目录检查唯一 PRIMARY、回执
> revision、报告路径、部门终态和 summary 一致性；不能只检查开关为 true。为每项门禁增加至少
> 一个篡改或缺失负例，使用 Python 3.12 运行组织校验、测试、仓库校验和 `git diff --check`，再
> 提交研发报告供集成审查。

## 7. 当前场景是否有更优方案及一次解决的提示词

更优方案是先把组织合同拆成两层可独立验收的 validator：第一层严格校验静态组织 Schema 和全部
硬字段；第二层读取结构化任务证据，校验路径、身份索引、revision、Git 祖先与状态收口。在线线程
真实性仍由来源主线程复核。每个 TOML `require_*` 字段必须映射到一个实现函数和一个失败测试，
从设计上消除“配置声称已检查、代码实际未检查”的空间。

一次解决的更优提示词：

> 请将 MacroLens 治理校验实现为 schema validator、task-evidence validator 和 online evidence
> verifier 三层。先定义唯一的 department file slug 并迁移当前任务证据；为 TOML 每个必填字段和
> `require_*` 开关建立实现函数、错误码和负向测试映射。schema 层验证版本、部门、路由、触发器、
> 回执字段、状态与路径模板；task 层验证一个 PRIMARY、所有 SUPPORTING、回执 revision/hash、
> report/summary 身份、Git 祖先和终态；online 层只验证真实线程事件。只有前两层全绿才允许集成，
> 最终 summary 只有在线层通过才可声明 `THREAD_EVIDENCE_VERIFIED`。
