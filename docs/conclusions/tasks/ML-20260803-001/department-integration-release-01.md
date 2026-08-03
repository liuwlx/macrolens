# ML-20260803-001 集成发布部 01 报告

## 报告元数据

- Contract version：`2`
- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`82459dc`
- 当前接受范围：`复审 86572b61 的十源显式映射、pre-integration 与 post-integration 零重复集成重入证明和 96 项门禁；通过后依次集成十个研发 direct commit 并更新 contract v2 集成报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-09.md`
- 实际范围：复审 `86572b61` direct patch、十源显式映射、source/main 祖先语义、首次十次集成与第二次零新增重入及 96 项门禁；在最新 main 上复现 P1 后停止。
- 审查基线：`7e54f252fab1fce0f87ce04fb0b32c8e9cba8d1b`
- 研发候选提交：`d1e5b40804805e67681893af63cffd83fd0000e5`、`c9353fd1ed639bd84f0668dd57c50283435b65f7`、`6a0b5b6d71b95140eaf1da524ba59befb63c20cd`、`c1bcdac55a7b0238fbea0d3cafe391c0bf22bf64`、`3c343b44a063f780afc16adccb96eb92758d3076`、`12766ea0f6bb1ae967b0c98525025bef4dace60a`、`bac5d0883d59d8ff7244e34a89631a3b05d7478a`、`b05bfac2344d0816ecb2a85dfa38976e3096a0a6`、`363354ee84e307594746d4093572ebcdbf784fd6`、`86572b61442aae11b57bb50c5055c15ba62b1025`
- 明确排除的同步 merge：`18ef5a4`、`fa486e0` 及此前全部同步提交
- 集成方式：十个候选提交均未 cherry-pick；候选前 96 项测试门禁 fail closed
- 集成提交：`N/A`
- Git 冲突：未进入 cherry-pick，因此无 Git 冲突
- 合同冲突：存在，详见“集成复审轮次 09”
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

## 集成复审轮次 03（remediation-03）

### v2 报告身份与执行元数据

- Contract version 目标：`2`（候选未通过集成门禁，main 当前合同仍为 v1）
- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`aa0d6d7`
- 当前接受范围：`复审完整研发分支与前两次阻塞整改，验证 2 正例加 36 负例、完整证据生命周期和直接测试命令；通过后由集成发布部合入 main 并更新报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-03.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`bb6df3ba7fe00f000c17618ee42cf8263acf7596`
- 审查候选：`d1e5b408`、`c9353fd1`、`6a0b5b6d`
- 明确排除：同步 merge `0e353ac`、`4ba5f82`
- 实际范围：完整审查六个治理文件、验证两轮恢复条件、在候选 worktree 重跑门禁；未修改候选或产品范围
- 产物/commits：本报告更新；三个候选提交均未 cherry-pick
- 集成 commit：`N/A`
- 报告更新 commit：本文件无法自引用最终 SHA，准确值记录在本席位交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### Standards 轴

只读 Standards Agent 报告 5 个硬缺陷：

1. main 任务卡使用 `REINTEGRATION_03_RESERVED` 和 `REVIEW_RUNNING`；候选 validator/TOML 均不
   允许，按三笔提交 cherry-pick 后组织校验必失败。
2. 合法显式 `ACTIVE/BLOCKED` 回执无法通过：严格字段集禁止成功字段，但后续公共 identity 逻辑
   又强制 `source_thread_id/task_card_path/task_card_revision`。
3. 任意新回执只要省略 `Evidence status` 就会降级为 active `LEGACY`，绕过 v2 完整字段；实现
   没有按提交时间、合同版本或白名单限定“v2 前历史回执”。
4. Git 时序只使用回执文件首次引入提交并校验到最新报告，未绑定当前回执内容提交，也未验证
   receipt 早于对应 implementation/remediation commit。
5. 完整报告身份只在报告自称 Contract version 2 时执行；删除该字段即可降级绕过 title、source、
   revision、scope、receipt 和 department code 等 v2 门禁。

判断项：1371 行 validator 同时承担 TOML Schema、Markdown、Git 生命周期与 report/summary
校验，存在可能的 Divergent Change；其余 Fowler smell 无需报告。

### Spec 轴

只读 Spec Agent 独立报告 4 项阻塞：

1. 最新 main 的任务/部门结果状态与候选封闭枚举不兼容，集成后无法通过必需检查。
2. `LEGACY` 自动降级允许新证据绕过完整 status-specific 字段，不满足任务卡成功标准 2、6 与
   `7bdf1e6` 恢复条件。
3. AGENTS 要求 receipt 先于 implementation 和 report；实现只有 revision→receipt→report，缺少
   receipt→implementation/remediation 的验证与负例。
4. 报告可通过删除 Contract version 降级；summary 虽检查七章和若干关键词，但未验证回执、
   commits、集成证据与部门结果明细，未落实完整 identity/证据合同。

两轴汇总：Standards 5 个硬缺陷，最严重为最新 main 状态导致集成后必失败；Spec 4 个阻塞，
最严重为同一状态不兼容与 LEGACY 降级绕过。两轴均结论 `BLOCKED`，无范围扩张发现。

### 7bdf1e6 恢复条件逐项核验

| 恢复条件 | 状态 | 证据 |
| --- | --- | --- |
| status-specific 成功字段 | **部分通过** | 显式 ACTIVE/RESERVED 使用十字段严格集合，十个缺字段负例存在；但新回执可省略 Evidence status 降级 LEGACY。 |
| status-specific 失败字段 | **未通过** | 单元级严格集合正确，但完整 ACTIVE/BLOCKED 流程随后又强制三个成功 identity 字段，形成不可满足合同。 |
| ACTIVE/LEGACY/INVALIDATED/SUPERSEDED | **部分通过** | INVALIDATED/SUPERSEDED 审计语义和当前失效回执可解析；LEGACY 缺少“仅 v2 前历史”的不可绕过边界。 |
| revision 实体 | **通过** | revision 必须解析为 commit，且该 commit 的任务卡路径与 task ID 必须匹配。 |
| 祖先时序 | **未通过** | revision→receipt 和 receipt→latest report 已实现；current receipt content commit 与 receipt→implementation/remediation 未实现。 |
| 完整 report identity | **未通过** | v2 报告字段检查存在，但可删除 Contract version 降级；department code 仍可缺失。 |
| 完整 summary/终态 | **部分通过** | 七章、来源身份、报告引用、成功标准/checks/evidence/risks 关键词和终态已检查；回执、commits、集成证据及部门结果明细未检查。 |
| direct test | **通过** | 原样直接脚本入口通过。 |
| 2 正例 + 36 负例 | **数量通过、覆盖未通过** | 输出计数准确，但 36 个负例未覆盖最新状态兼容、LEGACY 新证据降级、完整 BLOCKED 流程、receipt→implementation、报告删除 Contract version 等绕过。 |

### 候选 worktree 检查

- 候选 `HEAD`：`6a0b5b6d71b95140eaf1da524ba59befb63c20cd`；检查前后
  `git status --short` 无输出。
- `py -3.12 --version`：`Python 3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：通过，输出
  `STATIC_CONSISTENT: MacroLens organization contract v2`；该 worktree 仅同步至 `b469202`，
  不包含 main 的 remediation-03 状态和回执。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：通过，`Ran 38 tests`，输出
  `TEST_COUNTS: positives=2 negatives=36 total=38`。
- `py -3.12 -X utf8 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：
  通过，字节码定向到系统临时目录。
- `py -3.12 -X utf8 scripts/validate_repository.py`：使用只读临时 `PYTHONPATH` 指向现有 Python
  3.11 PyYAML site-packages 后通过，输出 `Repository contract valid: 61 source series, 62 API paths`；
  未安装或修改全局依赖。
- 候选 `git diff --check`：通过。

### 最新 main 兼容预检

直接加载候选 validator，对 `main@bb6df3b` 的当前任务目录执行只读 task-evidence 校验，得到
4 个错误。其中两个会在 cherry-pick 后仍然存在：

- `unknown task status 'REINTEGRATION_03_RESERVED'`
- `unknown department result status 'REVIEW_RUNNING'`

另外两个预检错误（候选研发报告尚未出现在 main、remediation-03 回执尚未早于本报告最新提交）
本可分别由 cherry-pick 和报告提交消除，但不能消除上述状态合同冲突。因此未开始 cherry-pick。

### 风险、阻塞与恢复条件

- 直接集成会使 main 必需组织门禁失败，并留下 LEGACY 与 Contract version 两条降级绕过路径。
- 恢复条件：候选必须与最新 main 使用同一机器状态枚举，或由来源主线程在新 revision 中改为既有
  合法状态；ACTIVE/BLOCKED 完整流程必须可满足；LEGACY 必须由不可伪造的历史边界限定；时序必须
  验证当前 receipt commit 早于对应 implementation/remediation；v2 报告不得通过删版本降级；
  summary 必须校验回执、commits、集成证据和部门结果明细，并增加对应负例。
- 修正后重新同步最新 main 证据，再派发下一轮集成。不得靠集成部门改写 task-card 或回执规避。

## 集成复审轮次 04（remediation-04）

### v2 报告身份与执行元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`99196e1`
- 当前接受范围：`复审 c1bcdac5 对第三轮全部阻塞的修复，验证 5 正例加 46 负例和正式状态机；通过后依次集成四个研发提交并更新集成报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-04.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`aaae62213245e8c1ce98432fb440b9085d687cc7`
- ACTIVE 回执 commit：`096b5faac6a3809ac4112f607ead471f1f70fd3e`
- 审查候选：`d1e5b408`、`c9353fd1`、`6a0b5b6d`、`c1bcdac5`
- 明确排除：同步 merge `0e353ac`、`4ba5f82`、`431023d`
- 实际范围：复审 `c1bcdac5^..c1bcdac5` 的六个授权文件，核验第三轮恢复条件、正式状态机和完整证据生命周期，并在候选 worktree 运行指定门禁。
- 四个 cherry-pick 新 SHA：`N/A`、`N/A`、`N/A`、`N/A`（硬门禁失败，未进入集成）
- 报告更新 commit：本文件不能自引用；准确 SHA 记录在本席位交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### 第三轮恢复条件复核

| 恢复条件 | 状态 | 证据 |
| --- | --- | --- |
| ACTIVE/BLOCKED 状态特定字段 | **通过** | 完整 BLOCKED 正例可满足；RESERVED 与 BLOCKED 使用不同严格字段集。 |
| LEGACY cutoff 与 current-content commit | **通过** | 缺失/显式 LEGACY 都受固定 cutoff 和当前 blob 内容提交约束。 |
| 正式状态机 | **通过** | 任务与部门结果已移除临时整改状态，只接受正式封闭枚举。 |
| v2 report/summary 防降级 | **通过** | cutoff 后删除或降级 Contract version 会失败，完整 identity/receipt/commit/result/integration evidence 被校验。 |
| direct test 与 5 正例 + 46 负例 | **通过** | 原样直接命令实测 `Ran 51 tests`，输出 `positives=5 negatives=46 total=51`。 |
| receipt→implementation 完整成功生命周期 | **未通过** | `_task_commit_map()` 对 `integration_release` 只映射轮次 0、2、3；当前 ACTIVE remediation-04 回执没有轮次 4 映射。`RUNNING` 可临时用最新报告内容提交兜底，但结果改为 `SUCCEEDED` 后兜底关闭，必报无对应 implementation/remediation commit。 |

### 独立 Standards / Spec 复审

- Standards Agent：报告 1 个 P1 硬缺陷，即成功终态无法把 remediation-04 ACTIVE 回执映射到
  本轮集成/报告提交。该缺陷不是当前样本自洽问题，而是来源主线程正常收口时必现的生命周期失败。
- Spec Agent：对固定 direct patch `c1bcdac5^..c1bcdac5` 报告 zero findings，确认第三轮显式恢复项、
  51 项测试和六文件范围本身均符合规格。
- 主席位复核：直接调用候选 `_task_commit_map()` 读取当前任务卡，实际输出仅含键
  `{0, 2, 3}`，`remediation-04 mapped: False`。结合 `_validate_task_directory()` 仅在
  `assignment.result_status == "RUNNING"` 时启用报告 fallback，确认 Standards finding 成立。

### 候选检查与最终判断

- 候选 worktree：`codex/ml-20260803-001-engineering-04@c1bcdac55a7b0238fbea0d3cafe391c0bf22bf64`，检查前后干净。
- Python：`3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：通过，输出
  `STATIC_CONSISTENT: MacroLens organization contract v2`；这只证明候选当前 `RUNNING` 快照。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：通过，`5` 正例、`46` 负例、共 `51` 项。
- `py -3.12 -X utf8 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：通过。
- `py -3.12 -X utf8 scripts/validate_repository.py`：Python 3.12 默认环境缺少 `yaml`；仅对该只读进程设置
  `PYTHONPATH=D:\开发环境\运行时\Python\Python311\Lib\site-packages` 后通过，输出
  `Repository contract valid: 61 source series, 62 API paths`，未安装或修改依赖。
- 候选 `git diff --check`：通过。
- 范围检查：四个 direct commit 各自仅修改任务卡授权的六个文件；三个同步 merge 均未纳入候选集成序列。
- 首次报告提交 `2def2c6588c1247bbe0d7dfb1f12221c31989d5a` 后在实际 main 原样运行组织校验、
  直接测试和 `py_compile`：三项均因候选未集成、对应两个脚本在 main 不存在而退出 `1`；这不是
  候选测试失败，也不能表述为 main 已达到 `STATIC_CONSISTENT`。同一 main 上
  `validate_repository.py` 使用上述只读 `PYTHONPATH` 后通过，`git diff --check` 通过。
- 最终判断：`BLOCKED`。不把“当前 RUNNING 快照可绿”误当作“SUCCEEDED 生命周期可收口”，因此四个研发提交均未写入 main。

### 风险与恢复条件

- 风险：若现在集成，来源主线程把集成发布部结果从 `RUNNING` 更新为 `SUCCEEDED` 后，组织门禁会
  因 remediation-04 ACTIVE 回执没有对应提交映射而失败，主任务无法形成稳定终态。
- 恢复条件：为 `integration_release` 的每个 remediation 轮次定义可持续的任务卡提交字段/解析规则，
  至少支持本轮成功集成提交或报告提交，并增加一个从 `RUNNING` 更新到 `SUCCEEDED` 后仍
  `STATIC_CONSISTENT` 的真实 Git 正例及缺失映射负例；然后重新派发集成复审。

## 集成复审轮次 05（remediation-05）

### v2 报告身份与执行元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`459efbf`
- 当前接受范围：`复审 3c343b44 的成功生命周期修复与 9 正例加 51 负例；通过后依次集成五个研发提交，更新 contract v2 集成报告并返回 integration commit 与 report commit。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-05.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`42d9b484b0d01bf6324936f5c34f77549f8221ae`
- ACTIVE 回执 commit：`6c145f2ebd926ab92a321158a879e71ecf662a6e`
- 审查候选：`d1e5b408`、`c9353fd1`、`6a0b5b6d`、`c1bcdac5`、`3c343b44`
- 明确排除：全部同步 merge，包括 `0e353ac`、`4ba5f82`、`431023d`、`6cf81f8`
- 实际范围：固定复审 `3c343b44^..3c343b44` 的六个授权文件；核验运行态、缺双 SHA、错 SHA、不可解析/非祖先、完整双 SHA 后 REVIEW、最终 summary 和真实 cherry-pick 拓扑。
- 五个 cherry-pick 新 SHA：`N/A`、`N/A`、`N/A`、`N/A`、`N/A`（硬门禁失败，未进入集成）
- Integration commit：`N/A`
- Integration report commit：本文件不能自引用；本轮 BLOCKED 报告的准确 SHA 记录在交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### Standards 轴

Standards Agent 报告 3 个 P1 硬缺陷，Fowler 判断项 0：

1. 成功状态门禁只拒绝 task=`RUNNING`，没有强制 task 必须为 `REVIEW`。实测
   `DRAFT`、`DISPATCHING`、`READY`、`SUCCEEDED`、`FAILED`、`BLOCKED` 配合 integration
   result=`SUCCEEDED` 和格式完整双 SHA 都得到零错误，违反候选自身规定的正式迁移顺序。
2. 最终 summary 与明确的 cherry-pick 拓扑不闭合。summary Git 校验要求任务卡声明的五个原候选
   SHA 都是 summary 的祖先；这些 SHA 当前均不是 main 祖先，cherry-pick 只会产生新 SHA，不会让
   原提交成为祖先。新增 final-summary 正例使用 `verify_git=False`，未覆盖真实 Git 门禁。
3. assignment execution 的 report fallback 被扩展到所有部门和结果状态；规则只允许
   `RUNNING`、`FAILED`、`BLOCKED` 使用该兜底，因此非集成部门 `SUCCEEDED` 时也能缺失显式执行
   映射而通过。

### Spec 轴

Spec Agent 报告 1 个 P1 硬缺陷：`_validate_integration_success_mapping()` 仅在 task 为 `RUNNING`
时报“不能在 REVIEW 前成功”，而不是要求 task 精确为 `REVIEW`。51 个负例只有 RUNNING 提前成功
用例，没有覆盖其他非法任务状态。因此“完整双 SHA 后 REVIEW”仍是可绕过的部分实现。其余
direct patch 只涉及六个授权文件，无范围扩张发现。

### 候选检查与最终判断

- 候选 worktree：`codex/ml-20260803-001-engineering-04@3c343b44a063f780afc16adccb96eb92758d3076`，检查前后干净。
- Python：`3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：通过，输出 `STATIC_CONSISTENT`。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：通过，`9` 正例、`51` 负例、共 `60` 项。
- `py -3.12 -X utf8 -m unittest scripts.test_validate_organization`：通过，`Ran 60 tests`。
- `py -3.12 -X utf8 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：通过。
- `py -3.12 -X utf8 scripts/validate_repository.py`：Python 3.12 默认环境缺少 `yaml`；仅对该只读进程设置 `PYTHONPATH=D:\开发环境\运行时\Python\Python311\Lib\site-packages` 后通过，输出 `Repository contract valid: 61 source series, 62 API paths`。
- 候选 `git diff --check`：通过。
- 范围检查：`3c343b44` 仅修改任务卡授权的六个文件；同步 merge 未纳入候选集成序列。
- BLOCKED 报告提交 `db0bca05ca912199c440480ad662087e4683a03c` 后在实际 main 原样运行 organization
  validator、direct tests、unittest 和 compile：因 fail-closed 未集成候选、两个脚本在 main 不存在，
  四项均退出 `1`，不能声明 main `STATIC_CONSISTENT`。同一 main 上 repository validator 使用上述
  只读 `PYTHONPATH` 后通过，`git diff --check` 通过，工作区干净。
- 最终判断：`BLOCKED`。测试数量与当前候选快照自洽不能覆盖正式状态机和真实 cherry-pick/summary Git 生命周期缺口，故五个研发提交均未写入 main。

### 风险与恢复条件

- 风险：若现在集成，非法任务状态可配合 integration `SUCCEEDED` 通过；即使来源线程遵循 REVIEW
  顺序，最终 summary 仍会因原候选 SHA 不是 cherry-pick 后 main 的祖先而失败；其他成功部门也可
  通过过宽 report fallback 绕过显式执行映射。
- 恢复条件：成功 integration 必须要求 task 精确为 `REVIEW`；为 cherry-pick 建立原候选 SHA 到
  main 新 SHA 的可验证映射，或让 summary 只对真正集成的 main SHA 执行祖先检查；将 report
  fallback 严格限制到规则声明的 `RUNNING/FAILED/BLOCKED`；增加真实 Git 仓库的 REVIEW→最终
  summary 正例，以及每个非法状态、cherry-pick 拓扑和 SUCCEEDED fallback 的负例。

## 集成复审轮次 06（remediation-06）

### v2 报告身份与执行元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`bc77335`
- 当前接受范围：`复审 12766ea0 与研发双轴自审，验证真实 cherry-pick 拓扑、正式 REVIEW/summary、非集成成功映射和 11 正例加 65 负例；通过后依次集成六个研发提交并更新报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-06.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`a517ba7add2f51ab9f347984b9520afa5a11a343`
- ACTIVE 回执 commit：`5d2a6cec16bf77953ae1c98319c75bd9e4cc6f84`
- 审查候选：`d1e5b408`、`c9353fd1`、`6a0b5b6d`、`c1bcdac5`、`3c343b44`、`12766ea0`
- 明确排除：全部同步 merge，包括 `0e353ac`、`4ba5f82`、`431023d`、`6cf81f8`、`d4217dc`
- 实际范围：固定复审 `12766ea0^..12766ea0` 的六个授权文件，并以候选 validator 对最新 main 任务证据执行只读兼容预检。
- 六个 cherry-pick 新 SHA：全部 `N/A`（存在 P1，未进入集成）
- Integration commit：`N/A`
- Integration report commit：本文件不能自引用；本轮 BLOCKED 报告的准确 SHA 记录在交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### Standards 轴

Standards Agent 报告 2 个 P1，Fowler 判断项 0：

1. **最新 main 与新门禁确定性不兼容。** `main@a517ba7` 的 Engineering 结果为 `SUCCEEDED`，
   但 task-card 没有 `Assignment execution mapping`。候选禁止成功部门使用 report fallback，要求
   每份 ACTIVE receipt 有显式 mapping；六个 direct commit 均不修改 task-card。候选 validator
   对最新 main 只读预检时，Engineering remediation-02～05 四份 ACTIVE receipt 全部报
   `ACTIVE receipt has no assignment execution commit mapping`。
2. **“只有 integrated SHA 可成为 summary 祖先”未执行。** 文档和 TOML 明确 source worktree
   commit 不应成为 final summary 祖先，但 validator 只正向要求 integrated/report commits 是祖先，
   没有反向拒绝 source candidate 已通过误 merge 进入 main。真实 cherry-pick 正例只由测试代码
   自行断言 source 非祖先，没有让 validator 执行该性质。

### Spec 轴

Spec Agent 报告 1 个 P1：派单要求报告提交后、task/result 仍为 `RUNNING` 且不修改 task-card 时
必须 `STATIC_CONSISTENT`；但候选只从 task-card mapping 表读取成功非集成部门映射，最新 main
不存在该表。候选 11 正例 + 65 负例虽然全部通过，但完整 Git 正例删除真实任务目录并仅构造单一
Integration assignment，没有覆盖当前“Engineering SUCCEEDED + Integration RUNNING”的真实拓扑。

### 最新 main 兼容预检

直接加载候选 `12766ea0` validator 与候选 TOML department 定义，对
`main@a517ba7` 的真实任务目录执行 `verify_git=True` 只读预检，得到 10 个错误：

- 4 个持久错误：Engineering remediation-02、03、04、05 ACTIVE receipts 均缺 assignment
  execution mapping。六个 direct commits 和本部门报告都不能消除这些错误。
- 1 个候选尚未进入 main 的瞬时错误：Engineering terminal report 缺失，cherry-pick 可消除。
- 5 个本轮报告尚未更新产生的瞬时错误：remediation-06 receipt 晚于旧报告，以及旧报告 revision、
  scope、receipt path 不匹配；本报告提交可消除。

由于仍有 4 个不可由授权范围消除的 P1 级持久错误，不启动 cherry-pick。

### 候选检查与最终判断

- 候选 worktree：`codex/ml-20260803-001-engineering-04@12766ea0f6bb1ae967b0c98525025bef4dace60a`，检查前后干净。
- Python：`3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：候选分支通过，输出 `STATIC_CONSISTENT`；该分支 task-card 使用 Engineering=`RUNNING`、Integration=`BLOCKED`，不是最新 main 状态。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：通过，`11` 正例、`65` 负例、共 `76` 项。
- `py -3.12 -X utf8 -m unittest scripts.test_validate_organization`：通过，`Ran 76 tests`。
- `py -3.12 -X utf8 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：通过。
- `py -3.12 -X utf8 scripts/validate_repository.py`：Python 3.12 默认环境缺少 `yaml`；仅对该只读进程设置 `PYTHONPATH=D:\开发环境\运行时\Python\Python311\Lib\site-packages` 后通过，输出 `Repository contract valid: 61 source series, 62 API paths`。
- 候选 `git diff --check`：通过。
- 范围检查：`12766ea0` 仅修改六个授权文件；必需 task-card mapping 不在六个 direct commits 中。
- BLOCKED 报告提交 `c14ac6e7f68a394a21135e4df0b70181a662d332` 后在实际 main 原样运行
  organization validator、direct tests、unittest 和 compile：因 fail-closed 未集成候选、两个脚本
  在 main 不存在，四项均退出 `1`，不能声明 main `STATIC_CONSISTENT`。同一 main 上 repository
  validator 使用上述只读 `PYTHONPATH` 后通过，`git diff --check` 通过，工作区干净。
- 最终判断：`BLOCKED`。候选自审的两个轴虽然报告 0 P1/P2，但没有以最新 main 的真实多部门任务证据完成集成前兼容验证。

### 风险与恢复条件

- 风险：若现在 cherry-pick，报告提交后仍会因四份 Engineering ACTIVE receipt 缺 mapping 而无法
  达到 `STATIC_CONSISTENT`；若 source candidate 通过误 merge 成为 summary 祖先，validator 也
  不会执行文档声明的反向禁止规则。
- 恢复条件：来源主线程先在正式新 revision 中为所有已 `SUCCEEDED` 非集成部门保存完整、真实且
  可验证的 receipt→source→integrated mapping，或由合同定义不需要追溯改造的明确迁移方案；候选
  必须在最新 main 多部门任务目录上跑通 `validate(verify_git=True)`，并增加 source candidate
  已成为 main/summary 祖先时必失败的 validator 负例。重新派发前不得靠集成部门改 task-card。

## 集成复审轮次 07（remediation-07）

### v2 报告身份与执行元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`9d5d4f0`
- 当前接受范围：`复审 b05bfac2、真实八轮多部门拓扑、LOCAL_REPORT assignment 隔离和 13 正例加 83 负例；通过后依次集成八个研发提交并更新 contract v2 报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-07.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`1f7469b0badb339956b9fcc2fed5c143df7b44bf`
- ACTIVE 回执 commit：`fc3db75`（回执文件当前内容提交）
- 审查候选：八个 direct commits，末两笔为 `bac5d088`、`b05bfac2`
- 明确排除：全部同步 merge，包括 `0e353ac`、`4ba5f82`、`431023d`、`6cf81f8`、`d4217dc`、`04507a5`、`ed180be6`
- 实际范围：固定复审 `bac5d088^..bac5d088` 与 `b05bfac2^..b05bfac2` 六个授权文件；重跑候选 96 项门禁并复核 LOCAL_REPORT 与八轮拓扑。
- 八个 cherry-pick 新 SHA：全部 `N/A`（存在 P1，未进入集成）
- Integration commit candidate：`N/A`
- Integration report commit candidate：`N/A`；本轮 BLOCKED 报告准确 SHA 记录在交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### Standards 轴

Standards Agent 报告 `P1=1, P2=0, P3=0`：真实八轮生命周期正例依赖可变 main 状态。
`scripts/test_validate_organization.py` 的正例硬编码把首个 Integration
`| RESERVED | BLOCKED |` 替换为 `RUNNING`，但正式 `main@1f7469b` 已经是 `RUNNING`，因此
`assertIn` 失败。该 Fragile Test / Mystery Guest 使候选没有实际证明当前八轮拓扑；无其他
Standards finding。

### Spec 轴

Spec Agent 同样复现候选 direct test 与 unittest 的 96 项套件各有 1 个 failure。派单明确要求
重跑并通过 13 正例 + 83 负例；计数文本虽打印 `positives=13 negatives=83 total=96`，但 suite
状态是 `FAILED`，因此不得用计数替代成功门禁。无证据支持进入八笔 cherry-pick。

### 候选检查与最终判断

- 候选 worktree：`codex/ml-20260803-001-engineering-04@b05bfac2344d0816ecb2a85dfa38976e3096a0a6`，检查前后干净。
- Python：`3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：通过，输出 `STATIC_CONSISTENT`。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：失败，退出 `1`；`Ran 96 tests`，1 failure，计数 `13/83/96`。
- `py -3.12 -X utf8 -m unittest scripts.test_validate_organization`：失败，退出 `1`；同一正例失败。
- `py -3.12 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：通过。
- `py -3.12 -X utf8 scripts/validate_repository.py`：Python 3.12 默认环境缺少 `yaml`；仅对该只读进程设置 `PYTHONPATH=D:\开发环境\运行时\Python\Python311\Lib\site-packages` 后通过，输出 `Repository contract valid: 61 source series, 62 API paths`。
- 候选 `git diff --check`：通过。
- 范围检查：`bac5d088`、`b05bfac2` 各自只修改六个授权文件；同步 merge 未纳入审查或集成序列。
- 最终判断：`BLOCKED`。用户规定任一 P1/P2 或 96 项门禁不通过即不集成；八个研发提交均未写入 main。

### 风险与恢复条件

- 风险：若忽略失败继续集成，门禁会把“测试数量正确”误作“真实八轮拓扑已证明”，而正例实际
  没有执行到 validator 生命周期断言。
- 恢复条件：让真实多部门生命周期 fixture 不依赖浮动 main 的旧状态文本；显式构造或幂等识别
  Integration=`RUNNING`，然后在正式最新 main 拓扑上让 direct test 与 unittest 均 96/96 通过。
  重新派发前保留 LOCAL_REPORT、非法/空/重复声明及 source 非祖先负例。

## 集成复审轮次 08（remediation-08）

### v2 报告身份与执行元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`4d77158`
- 当前接受范围：`复审 direct candidate 363354ee 的幂等 RUNNING fixture、动态活动证据集合和 13 正例加 83 负例；通过后依次集成九个研发 direct commit 并更新 contract v2 集成报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-08.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`8c88fb7376060d17cee4a2ad87d29fbe4944ab68`
- ACTIVE 回执 commit：`772cb94`（回执文件当前内容提交）
- 审查候选：九个 direct commits，最后一笔 `363354ee`
- 明确排除：全部同步 merge，包括 `fa486e02`、`0e353ac`、`4ba5f82`、`431023d`、`6cf81f8`、`d4217dc`、`04507a5`、`ed180be6`
- 实际范围：固定复审 `363354ee^..363354ee`，其 direct patch 仅修改测试脚本与研发报告；验证候选前及预期报告后的门禁语义。
- 九个 cherry-pick 新 SHA：全部 `N/A`（存在 P1，未进入集成）
- Integration commit candidate：`N/A`
- Integration report commit candidate：`N/A`；本轮 BLOCKED 报告准确 SHA 记录在交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### Standards 轴

Standards Agent 报告 `P1=1, P2=0, P3=1`：

- P1：真实生命周期 fixture 只接受 task-card 原生 order 0..7，再以当前 HEAD 人工补 order 8。
  候选阶段可通过；九次 cherry-pick 和报告提交后，main task-card 已原生声明 order 8=`363354ee`，
  该精确断言必失败。即使删除断言，复制授权文件无差异会让第九个 source 退化为当前
  main/report HEAD，无法作为独立 source 再 cherry-pick。
- P3（Duplicated Code）：动态收集 ACTIVE/LEGACY receipt 的同形测试逻辑出现两次，可后续抽取
  helper；不影响本轮阻断判断。

### Spec 轴

Spec Agent 报告 `P1=1, P2=0, P3=0`：`scripts/test_validate_organization.py` 的真实生命周期
正例只在 candidate worktree 可通过。派单要求九笔集成及报告提交后从 main 原样再跑 96 项；届时
clone 初始 HEAD 已是 main/report commit，测试会错误重写第九个 source 并再次 cherry-pick 0..8，
产生空提交或冲突。幂等状态 helper 和动态证据枚举本身未发现其他缺口。

### 候选检查与最终判断

- 候选 worktree：`codex/ml-20260803-001-engineering-04@363354ee84e307594746d4093572ebcdbf784fd6`，检查前后干净。
- Python：`3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：通过，输出 `STATIC_CONSISTENT`。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：通过，`Ran 96 tests`，`13` 正例、`83` 负例。
- `py -3.12 -X utf8 -m unittest scripts.test_validate_organization`：通过，`Ran 96 tests`。
- `py -3.12 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：通过。
- `py -3.12 -X utf8 scripts/validate_repository.py`：Python 3.12 默认环境缺少 `yaml`；仅对该只读进程设置 `PYTHONPATH=D:\开发环境\运行时\Python\Python311\Lib\site-packages` 后通过，输出 `Repository contract valid: 61 source series, 62 API paths`。
- 候选 `git diff --check`：通过。
- 范围检查：`363354ee` 只修改研发报告与测试脚本；同步 merge 未纳入候选集成序列。
- 最终判断：`BLOCKED`。候选前门禁全绿，但报告后同一门禁确定性失败，违反派单第 5 项，故九个研发提交均未写入 main。

### 风险与恢复条件

- 风险：若现在集成，会在报告提交后才发现真实生命周期正例无法重入，留下已写入 main 但不能通过
  强制门禁的状态。
- 恢复条件：fixture 必须固定 source candidate 集合，不从运行时 ROOT/HEAD 推导最后一个 source；
  在 baseline 已包含九个 integrated commits 和报告时，不得再次 cherry-pick，而应验证已有
  source→integrated patch-id/祖先证据。增加 post-integration main 运行的显式正例，并保证候选前与
  报告后两个阶段均 96/96 通过。

## 集成复审轮次 09（remediation-09）

### v2 报告身份与执行元数据

- 任务 ID：`ML-20260803-001`
- 角色：`SUPPORTING`
- 部门代码：`integration_release`
- 线程标题：`ML｜集成发布部｜席位｜01`
- 线程 ID：`019fc533-b3a2-7be2-96ce-f4990bda6d6e`
- 来源主线程：`ML | 项目统筹部 | 主线程 | 01`
- 来源线程 ID：`019fc3a3-d0a0-7f13-b660-2010e36c7138`
- 当前接受的任务卡 revision：`82459dc`
- 当前接受范围：`复审 86572b61 的十源显式映射、pre-integration 与 post-integration 零重复集成重入证明和 96 项门禁；通过后依次集成十个研发 direct commit 并更新 contract v2 集成报告。`
- 当前回执证据：`docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-09.md`
- 报告路径：`docs/conclusions/tasks/ML-20260803-001/department-integration-release-01.md`
- 复审开始 main：`7e54f252fab1fce0f87ce04fb0b32c8e9cba8d1b`
- ACTIVE 回执当前内容 commit：`7e54f252fab1fce0f87ce04fb0b32c8e9cba8d1b`
- 审查候选：十个 direct commits，最后一笔 `86572b61442aae11b57bb50c5055c15ba62b1025`
- 明确排除：全部同步 merge，包括 `18ef5a4`、`fa486e0` 及此前列出的同步提交
- 实际范围：固定复审 `86572b61^..86572b61`，验证十源显式映射、source !→ main、main → source、首次十次集成、第二次零新增重入及最新 main 的 96 项门禁。
- 十个 cherry-pick 新 SHA：全部 `N/A`（存在 P1，未进入集成）
- Integration commit candidate：`N/A`
- Integration report commit candidate：`N/A`；本轮 BLOCKED 报告准确 SHA 记录在交付回复
- Git 冲突：未开始 cherry-pick，因此无 Git 冲突
- 最终席位状态：`BLOCKED`
- 部门结果：`BLOCKED`

### Standards 轴

Standards Agent 报告 `P1=1, P2=0, P3=0`：真实生命周期测试从最新 main 解析出的
`declared_source_baseline` 已含 order 0..9，但 `scripts/test_validate_organization.py:1271-1288`
仍断言只能是 order 0..8。定向测试在第 1275 行失败，尚未执行十次 patch-id 集成、第二次零新增
重入、source/main 祖先关系与最终 summary 断言。direct patch 只改测试脚本和研发报告，
`git diff --check` 通过，未发现额外 Fowler smell。

### Spec 轴

Spec Agent 报告 `P1=1, P2=0, P3=0`：当前 `main@7e54f25` 的任务卡已经显式声明
order 9=`86572b61`，而候选测试仍按旧阶段基线期待 0..8，再合成第十项。direct 96 项实跑
虽输出 `13` 正例、`83` 负例和总数 `96`，但有 1 个 failure；所谓 post-integration 零新增重入
未在真实 ten-source/latest-main 输入上得到证明，不能满足报告后同一门禁重跑要求。

### 候选检查与最终判断

- 候选 worktree：`codex/ml-20260803-001-engineering-04@86572b61442aae11b57bb50c5055c15ba62b1025`，检查前后干净。
- Python：`3.12.9`。
- `py -3.12 -X utf8 scripts/validate_organization.py`：通过，输出 `STATIC_CONSISTENT`。
- `py -3.12 -X utf8 scripts/test_validate_organization.py`：失败；`Ran 96 tests`，`13` 正例、`83` 负例，`failures=1`。
- `py -3.12 -X utf8 -m unittest scripts.test_validate_organization`：失败；`Ran 96 tests`，同一正例 `failures=1`。
- `py -3.12 -m py_compile scripts/validate_organization.py scripts/test_validate_organization.py`：通过。
- `py -3.12 -X utf8 scripts/validate_repository.py`：Python 3.12 默认环境缺少 `yaml`；仅对该只读进程设置 `PYTHONPATH=D:\开发环境\运行时\Python\Python311\Lib\site-packages` 后通过，输出 `Repository contract valid: 61 source series, 62 API paths`。
- 候选 `git diff --check`：通过。
- 范围检查：`86572b61` 只修改研发报告与测试脚本；同步 merge 未纳入候选集成序列。
- 最终判断：`BLOCKED`。候选前正式 96 项门禁已经失败，故十个研发提交均未写入 main。

### 风险与恢复条件

- 风险：若忽略失败继续集成，会把未证明的十源拓扑与重入路径写入 main；报告后的相同测试仍会
  在 fixture 初始化阶段失败，无法作为集成完成证据。
- 恢复条件：测试必须以显式阶段模型处理任务卡已声明当前 source 的正式输入；pre-integration
  阶段应验证十个固定 source 尚未成为 main 祖先，post-integration 阶段应从显式 source→integrated
  映射验证 patch-id、main 祖先关系和零新增，而不能要求浮动任务卡回退到九源集合。direct 与
  unittest 两个入口均须在最新 main 上 96/96 全绿后再派发。

## 1. 本次遇到的问题以及场景

本席位负责把研发治理合同提交集成到 `main`，同时守住变更范围、合同同步和发布门禁。候选提交
表面上通过研发侧静态校验，但完整 diff 审查发现 validator 的实际证明能力弱于 TOML 和文档声明，
并且多词部门报告路径与当前任务证据发生冲突。若继续 cherry-pick，`main` 会得到一个能够对部分
不合规状态输出 `STATIC_CONSISTENT` 的合同，因此按 fail-closed 规则停止集成。

复审轮次 02 面对的是同一候选经 `c9353fd` 整改后的重新集成。虽然 slug、任务目录遍历和单一
PRIMARY 已修复，但完整回执、Git 时序、报告/summary 合同和负例仍不完整；最新 main 的复审回执
也不在候选支持的证据生命周期中。因此本轮再次停止集成。

remediation-03 已让直接入口、2 正例 + 36 负例、revision 实体、INVALIDATED 审计和部分完整
identity 校验落地，但候选没有与最新 main 状态同步，且仍有 LEGACY/Contract version 降级、
ACTIVE/BLOCKED 矛盾和 implementation 时序缺口。第三轮因此继续 fail closed。

remediation-04 修复了第三轮列出的显式缺口，并把测试扩充到 5 正例 + 46 负例；然而独立 Standards
复审发现成功终态没有本轮 integration receipt 的提交映射。候选只能在 `RUNNING` 状态依靠报告
fallback 通过，一旦正常收口为 `SUCCEEDED` 即失败，因此仍不能进入基线。

remediation-05 引入双 SHA 成功映射并扩充到 9 正例 + 51 负例，但状态检查只排除 `RUNNING` 而未
强制 `REVIEW`；真实 cherry-pick 后的原候选提交也不满足 final summary 的祖先断言，且 report
fallback 对成功部门过宽。第五轮因此继续 fail closed。

remediation-06 引入 source→integrated patch-id 映射并扩充到 11 正例 + 65 负例，但候选自测所用
task-card 状态与最新 main 不同。最新 main 的成功研发席位没有新合同要求的 mapping，六个 direct
commits 又不修改 task-card；因此集成后 RUNNING 过渡态仍会确定性失败。

remediation-07 将 Engineering 恢复为 RUNNING，引入 source 隔离与 LOCAL_REPORT 路径，并声明
13 正例 + 83 负例；但真实八轮多部门正例仍假定 Integration 旧状态为 BLOCKED。最新任务卡已是
RUNNING，导致 direct 与 unittest 都出现 1 个 failure，第七轮按硬门禁停止。

remediation-08 修复了 RUNNING fixture 对 BLOCKED 字符串的依赖，候选前 96 项全绿；但测试仍从
当前 ROOT/HEAD 推导第九个 source 并重复 cherry-pick。报告提交后的 main 已含九笔集成，此时同一
测试不能重入，因此第八轮继续 fail closed。

remediation-09 引入十源显式映射与零新增重入路径，但正式 main 的任务卡在开工前已经声明第十个
source。测试仍断言运行时来源集合只能包含前九项，导致 direct 与 unittest 的 96 项门禁各有
1 个 failure，且在真正的十次集成与重入断言前退出。第九轮因此继续 fail closed。

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

第三轮以 `512179f...6a0b5b6` 的六个授权文件为完整审查面，并把三笔直接研发提交与两个同步
merge 分开。除再次运行两轴审查和候选门禁外，还直接加载候选 validator 对 `main@bb6df3b`
任务证据预检，从而在不修改 main 的情况下证明 cherry-pick 后的确定性失败。

第四轮将 `c1bcdac5^..c1bcdac5` 固定为 direct patch，排除 `431023d` 同步 merge；候选门禁全绿后，
继续检查从当前 `RUNNING` 到正式 `SUCCEEDED` 的状态迁移。通过直接读取 `_task_commit_map()` 结果
与 fallback 条件，证明轮次 04 缺少可持续提交映射，避免把瞬时快照通过误判为生命周期通过。

第五轮将 `3c343b44^..3c343b44` 固定为 direct patch，并同时执行函数级状态矩阵与真实 Git 祖先
检查。状态矩阵证明除 `RUNNING` 外的非法状态没有被拒绝；祖先检查证明五个原候选 SHA 均不是
main 祖先，从而暴露 verify_git=False 正例没有证明最终 summary 可收口。

第六轮除固定 `12766ea0^..12766ea0` direct patch 和运行候选门禁外，还直接加载候选 validator，
以 `verify_git=True` 校验最新 main 的真实任务目录。该步骤把候选自洽与可集成性分离，定位出
四个不会由 cherry-pick 或报告提交消失的 execution mapping 错误。

第七轮固定 `bac5d088` 与 `b05bfac2` 两个 direct patch，排除同步 merge 后原样运行全部候选门禁。
两个测试入口都在同一真实多部门正例的 fixture 准备阶段失败，说明测试没有执行到八轮 patch-id、
LOCAL_REPORT 和 summary 的端到端断言，不能以计数行代替 suite 成功。

第八轮固定 `363354ee^..363354ee` direct patch，分别等待 direct 与 unittest 超过 30 秒完成，确认
候选前 96/96 通过。随后按派单要求反推报告后再次运行的输入状态，发现测试会把 main/report HEAD
当 source 并重复集成，从而识别阶段相关假阳性。

第九轮固定 `86572b61^..86572b61` direct patch，并直接以最新 `main@7e54f25` 的任务证据运行
96 项门禁。两条入口均在 source map 等值断言处稳定失败；Standards/Spec 两轴独立确认这是最新
main 兼容性的 P1，而非环境波动或测试计数误差。

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

第三轮先验证候选自洽和测试计数，再验证候选对最新 main 的兼容性。由于 task/result 状态、
LEGACY 边界和完整生命周期仍有硬缺陷，未执行三笔 cherry-pick；只更新本报告并将恢复条件交还
来源主线程。

第四轮先验证 51 项测试和全部候选门禁，再执行两轴独立复审，并额外推演正常终态转换。发现
remediation-04 回执无法在 `SUCCEEDED` 状态映射到对应集成提交后，按 fail closed 不执行四笔
cherry-pick，只更新本报告并给出最小恢复条件。

第五轮先验证 60 项候选测试和全部候选门禁，再执行两轴独立复审与真实 Git 拓扑检查。三类硬
缺陷使正式 REVIEW、SUCCEEDED 和 summary 链路不能稳定闭合，因此不执行五笔 cherry-pick，只
更新本报告并交还最小恢复条件。

第六轮先验证 76 项候选测试、研发自审结论和六文件范围，再执行独立双轴复审与最新 main 兼容
预检。发现持久 P1 后不执行六笔 cherry-pick，只更新本报告，并把 task-card mapping 修复交还
来源主线程调度。

第七轮在任何 cherry-pick 前运行 96 项候选门禁和双轴复审；direct 与 unittest 均失败，两个轴各
报告 1 个 P1。按派单立即停止，不执行八笔 cherry-pick，只提交本部门 BLOCKED 报告。

第八轮候选前门禁通过后继续完成双轴复审；两个轴独立确认报告后重跑必失败的 P1。为避免先污染
main 再发现失败，不执行九笔 cherry-pick，只提交本部门 BLOCKED 报告。

第九轮在任何 cherry-pick 前先运行候选正式门禁；direct 和 unittest 均为 96 项、1 个 failure。
两个审查轴各报告 1 个 P1 后立即停止，不执行十笔 cherry-pick，只更新并提交本部门 BLOCKED
报告。

## 4. 使用的 Agents、skills、tools 以及阅读文档

### Agents

- 主执行席位：`ML｜集成发布部｜席位｜01`。
- `standards_review` 子 Agent：只读检查仓库规范、组织硬门禁和 Fowler smell。
- `spec_review` 子 Agent：只读核对任务卡成功标准与架构/知识设计。
- `standards_re_review` 子 Agent：复审整改后的规范符合性和首次阻塞回归。
- `spec_re_review` 子 Agent：复审任务规格、最新 main 证据兼容性与负例要求。
- `standards_review_03` 子 Agent：第三轮复核机器状态、完整 BLOCKED 流程、LEGACY、时序与报告降级。
- `spec_review_03` 子 Agent：第三轮复核任务成功标准、两轮恢复条件和最新 main 兼容性。
- `standards_review_04` 子 Agent：第四轮复核成功终态生命周期与 Fowler 标准，发现轮次 04 提交映射缺口。
- `spec_review_04` 子 Agent：第四轮固定 direct patch 复核第三轮恢复条件、测试计数与范围，报告 zero findings。
- `standards_review_05` 子 Agent：第五轮复核正式状态、真实 cherry-pick/summary 祖先和 report fallback。
- `spec_review_05` 子 Agent：第五轮按任务卡核验双 SHA 后必须 REVIEW 的状态迁移规则。
- `standards_review_06` 子 Agent：第六轮复核最新 main 兼容性、source/integrated 祖先合同和代码规范。
- `spec_review_06` 子 Agent：第六轮核验派单要求的 RUNNING 过渡态及真实多部门任务拓扑。
- `standards_review_07` 子 Agent：第七轮复核 96 项门禁、八轮拓扑和测试稳定性。
- `spec_review_07` 子 Agent：第七轮核验 remediation-07 RUNNING 任务卡与指定验收条件。
- `standards_review_08` 子 Agent：第八轮复核候选前与报告后测试重入性及 Fowler smells。
- `spec_review_08` 子 Agent：第八轮核验派单要求的 post-integration 96 项门禁和九轮 source 身份。
- `standards_review_09` 子 Agent：第九轮复核最新 main 兼容性、十源真实拓扑和 Fowler smells。
- `spec_review_09` 子 Agent：第九轮核验十源显式映射、pre/post integration 重入与 96 项门禁。

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
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-03.md`
- 候选提交 `6a0b5b6d71b95140eaf1da524ba59befb63c20cd` 中第二轮整改后的全部 6 个文件
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-04.md`
- 候选提交 `c1bcdac55a7b0238fbea0d3cafe391c0bf22bf64` 中第三轮整改后的全部 6 个文件
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-05.md`
- 候选提交 `3c343b44a063f780afc16adccb96eb92758d3076` 中成功生命周期整改后的全部 6 个文件
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-06.md`
- 候选提交 `12766ea0f6bb1ae967b0c98525025bef4dace60a` 中集成证据生命周期整改后的全部 6 个文件
- 研发报告中的 remediation-05 双轴自审、真实 Git 测试与交接声明
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-07.md`
- 候选提交 `bac5d0883d59d8ff7244e34a89631a3b05d7478a` 与 `b05bfac2344d0816ecb2a85dfa38976e3096a0a6` 的全部 direct patch
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-08.md`
- 候选提交 `363354ee84e307594746d4093572ebcdbf784fd6` 的测试与研发报告 direct patch
- `docs/conclusions/tasks/ML-20260803-001/receipts/department-integration-release-01-remediation-09.md`
- 候选提交 `86572b61442aae11b57bb50c5055c15ba62b1025` 的测试与研发报告 direct patch

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
9. 候选自洽不等于可集成；必须使用最新 main 的真实证据执行 merge 前兼容预检。
10. “缺字段即 legacy”本身是降级接口，必须以不可伪造的提交边界或显式白名单约束。
11. Git 时序要绑定当前内容和对应产物，不能只使用文件首次引入提交与最新报告提交。
12. 门禁必须验证合法状态迁移而不只是当前快照；`RUNNING` 的兜底路径若在 `SUCCEEDED` 关闭，必须有
    终态正例证明证据映射仍成立。
13. “拒绝某个提前状态”不等于“强制唯一合法状态”；状态机门禁应使用允许集合或精确等值，并为
    每个非法状态建立参数化负例。
14. cherry-pick 会改变提交身份。凡 summary 以 Git 祖先关系证明“已集成”，必须验证 main 新 SHA，
    或显式保存原候选到新 SHA 的映射，不能对原候选 SHA 直接做祖先断言。
15. 合成仓库正例不能替代最新 main 兼容预检；治理合同改变既有证据要求时，必须在真实多部门任务
    目录上运行 `verify_git=True`，确认迁移所需证据已经存在或有明确兼容规则。
16. 同步 merge 中的任务状态不能成为 direct commit 自测的隐含前提；集成审查必须以目标 main 的
    task-card 和 receipts 为准，排除 merge 后重新验证所有硬门禁。
17. 测试计数是清单证据，不是通过证据；即使打印 13/83/96，只要 suite 有 failure 就必须阻断。
18. 克隆真实仓库的测试仍需控制输入状态。fixture 不应通过替换某个历史状态字符串来构造目标状态，
    应显式解析 assignment 并幂等设置，或使用固定 revision，避免浮动 main 形成 Mystery Guest。
19. 集成门禁测试必须同时证明 pre-integration 与 post-integration 两阶段；从当前 HEAD 推导 source
    identity 会在阶段切换后失真，source 集合应由固定任务卡字段或显式参数提供。
20. 测试“可重复运行”不仅是状态归一化幂等，还包括 Git 操作幂等；baseline 已含目标 patch 时不能
    再 cherry-pick，应切换为验证既有 patch-id 和祖先关系。
21. 显式 source 列表仍需显式阶段语义；正式任务卡已声明当前候选时，测试不能把“已声明”误判为
    “已集成”，应分别用祖先关系和 source→integrated 映射区分 pre/post integration。

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

针对本轮，更优的首次提示词还应明确：

> 请让真实 Git 生命周期测试以任务卡显式声明的全部 source 为固定输入，并区分“source 已声明”与
> “source 已集成”。pre-integration 必须证明全部 source 不是 main 祖先；首次集成必须按固定顺序
> 产生 source→integrated patch-id 映射；post-integration 必须只验证该映射、main 祖先关系和零新增，
> 不得再次 cherry-pick。测试必须在最新正式 main 上通过 direct 与 unittest 两个 96 项入口。
