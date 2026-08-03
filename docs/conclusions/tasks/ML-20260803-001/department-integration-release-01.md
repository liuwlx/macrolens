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

## 审查结论

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

## 检查、风险与恢复条件

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

## 1. 本次遇到的问题以及场景

本席位负责把研发治理合同提交集成到 `main`，同时守住变更范围、合同同步和发布门禁。候选提交
表面上通过研发侧静态校验，但完整 diff 审查发现 validator 的实际证明能力弱于 TOML 和文档声明，
并且多词部门报告路径与当前任务证据发生冲突。若继续 cherry-pick，`main` 会得到一个能够对部分
不合规状态输出 `STATIC_CONSISTENT` 的合同，因此按 fail-closed 规则停止集成。

## 2. 分析这个问题的过程

先核对指定工作目录、`main`、干净状态和精确 HEAD，再确认研发基线是当前 main 的祖先，候选只
触及 6 个授权文件。随后完整读取任务卡、架构部、知识管理部和研发部报告，逐文件阅读候选 diff，
并把审查拆成规范轴和规格轴。规范轴将实现与根规则、TOML 和组织手册对照；规格轴将实现与任务卡
成功标准以及架构/知识设计逐条对照。两个轴独立得到相同核心结论：validator 存在可复现的声明与
实现落差，且路径合同未同步。

## 3. 解决这个问题的工作流程

1. 固定基线 `8c52c63` 和候选 `d1e5b40`，验证工作区与提交关系。
2. 核对候选变更文件集合，确认没有产品、API、Schema 或部署范围扩张。
3. 完整读取任务卡、三份部门报告和候选六文件 diff。
4. 分别执行 Standards 与 Spec 审查，汇总硬违规和判断项。
5. 运行当前基线可执行的仓库检查、工作区 diff 检查与候选 diff 空白检查，并记录 Python 版本。
6. 因硬门禁失败而不执行 cherry-pick，只写本席位独占报告并提交，保留 main 的可恢复干净状态。
7. 将修正范围和重新集成条件交还来源主线程调度，不代研发部修复，也不代测试部下结论。

## 4. 使用的 Agents、skills、tools 以及阅读文档

### Agents

- 主执行席位：`ML｜集成发布部｜席位｜01`。
- `standards_review` 子 Agent：只读检查仓库规范、组织硬门禁和 Fowler smell。
- `spec_review` 子 Agent：只读核对任务卡成功标准与架构/知识设计。

### Skills

- `code-review`：要求把规范符合性与规格符合性分轴独立审查。该流程直接暴露了 validator 假阴性
  和报告路径合同冲突，因而触发集成暂停。

### Tools

- `exec_command`：读取 Git、文档和候选文件，核对提交关系、版本及运行门禁。
- `apply_patch`：只创建本集成发布部报告。
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

## 5. 本次执行值得沉淀的经验或者模式

1. 校验器声明的门禁必须有实际执行路径，不能只验证“开关写成 true”。
2. 新增机器字段必须有唯一消费者；`report_slug` 与 `department_code` 并存但语义未贯通会制造
   视觉上不明显、机器上必然冲突的路径。
3. 正例通过只证明当前样本自洽；治理校验器必须用删除必填字段、错 revision、错路径、缺报告和
   错状态等负例证明 fail closed。
4. 集成部门应在写入基线前完成规格审查。可通过的测试不能覆盖已知规格缺口。
5. 静态一致性与真实线程身份是两种证明；明确边界是正确的，但静态一致性本身也必须完整实现。

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
