# Main Task Summary: ML-20260803-001

- Contract version: `2`
- Task ID: `ML-20260803-001`
- Source main thread: `ML｜项目统筹部｜主线程｜01`
- Source thread ID: `019fc3a3-d0a0-7f13-b660-2010e36c7138`
- Final status: `BLOCKED`
- Blocked phase: `remediation-10 integration assignment`
- Latest engineering source candidate: `036c8d7ef74efdd530cfab028d7dd9c2b83ad54a`
- Integration commit: `N/A`
- Quality result: `NOT_STARTED`

## 1. 本次遇到的问题以及场景

目标是把 MacroLens 的任务执行治理改成可验证流程：任务开始前必须有任务卡和真实部门回执，实际编码才创建 worktree；研发提交只能由集成发布部写入 main；参与部门各自提交报告，主线程最后汇总。

治理实现经过十轮研发整改和九轮独立集成复核。最新 direct candidate 已消除 source-map 固定轮次数量问题，并证明动态 N=11 首次集成、第二次零新增以及 13 正例加 83 负例。最终派发 remediation-10 集成复核时，部门线程服务发生系统错误，无法生成真实回执，因此任务按 fail-closed 规则停止。

## 2. 分析这个问题的过程

架构部先定义跨文件合同，知识管理部审查任务卡、回执、部门报告和主摘要证据。研发部在唯一实际编码阶段进入隔离 worktree。集成发布部每轮使用 Standards/Spec 双轴审查，在写入 main 前依次发现字段降级、状态迁移、source/integrated SHA 混淆、LOCAL_REPORT 隔离、浮动 main fixture、post-integration 重入和固定轮次假设等缺陷。

remediation-10 已把 source map、cardinality 和 current order 全部动态派生；direct 与 unittest 都是 96/96，双轴均为 0 P1/0 P2。随后连续尝试原席位 01、新建本地席位 02、同目录 fork 席位 02，三者均在回复前进入 `systemError`。这是部门执行通道不可用，不是候选代码失败。

## 3. 解决问题的工作流程

1. 注册任务卡并由架构部、知识管理部返回 RESERVED 回执和部门报告。
2. 仅在实际编码开始时创建研发 worktree；每轮整改均先回执、再开工、再提交 direct source candidate。
3. 每轮由集成发布部先双轴审查；发现 P1/P2 时提交 BLOCKED 报告且不 cherry-pick。
4. 最新研发 direct candidate 为 `036c8d7e`，同步 merge `7e144e9f909420ef13f014e4560381106f486a90` 明确禁止集成。
5. final integration 因三次线程级 `systemError` 无法获得回执；主线程没有越权集成，也没有派发测试部。
6. 恢复时应先获得 remediation-10 集成回执，再审查并依次集成任务卡声明的 11 个 direct sources，登记 source→integrated 映射和双 SHA，最后派测试部。

## 4. Agents、skills、tools 和阅读文档

### Agents

- 架构部席位 01：治理合同设计，结果 SUCCEEDED。
- 知识管理部席位 01：证据模型审查，结果 SUCCEEDED。
- 研发部席位 04：隔离 worktree 实现及十轮整改，最新候选检查通过，当前等待集成。
- 集成发布部席位 01：完成九轮 fail-closed 复核并提交九份阻塞证据；remediation-10 时线程故障。
- 集成发布部替补席位 02：新建与 fork 两种方式均在回执前发生系统错误。
- 测试部席位 01：依赖集成，尚未派发执行。
- 集成和研发审查子 Agents：按 Standards/Spec 两个只读轴复核。

### Skills

- `gpt-plan`：用于把治理要求整理成可执行、可校验合同。
- `code-review`：由研发与集成发布部执行 Standards/Spec 双轴审查。

### Tools

- Codex task/thread 工具：派单、等待、读取、替补席位创建与 fork。
- `apply_patch`、Git、PowerShell、Python 3.12。
- 组织 validator、repository validator、unittest、py_compile、git diff。

### 阅读文档

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- 本任务 task card、全部 receipts 和部门报告
- `gpt-plan/SKILL.md`、`code-review/SKILL.md`

## 5. 值得沉淀的经验或者模式

1. 回执必须来自目标部门原始线程事件；线程不可用时应 BLOCKED，不能由主线程代做。
2. 工作树只在真正编码时创建；设计、回执、报告和只读复核无需滥建 worktree。
3. 候选态通过不代表集成后通过，真实生命周期测试必须覆盖 pre-integration 与 post-integration 重入。
4. 测试夹具不能依赖浮动 main 的旧字符串、固定 receipt 清单或固定 remediation 数量；输入集合和 order 应动态解析并校验连续性。
5. cherry-pick 会改变 SHA，必须保存 source candidate→integrated main 的 patch-id 等价映射，并把 Integration commit 与 Integration report commit 分开记录。
6. 多轮阻断不是流程失败，而是集成门禁在 main 被污染前发挥作用。

## 6. 更好的初始提示词

> 请更新 MacroLens 的 AGENTS.md 和组织治理文件，使每个实质任务在开始前必须有任务卡、正确部门的真实 RESERVED 回执和明确成功标准；只有实际编码才把研发席位交给独立 worktree。研发只提交 source candidate，集成发布部双轴审查并 cherry-pick，主线程记录 source→integrated 映射，测试部在 main 上独立验收，最后各部门写报告、主线程写 summary。请同时实现 fail-closed validator，并用真实 Git 仓库测试 pre-integration、post-integration 重入、任意数量 remediation、LOCAL_REPORT 隔离、缺字段/错 revision/伪造回执等正负场景；任何部门线程不可用时返回 BLOCKED，禁止主线程代做。

## 7. 当前方案是否有更优方案及一次解决的提示词

更优方案是先冻结结构化 evidence schema，再实现纯函数状态机和 fixture builder，最后接 Git 与在线线程事件。测试数据应从任务卡动态生成，不读取浮动仓库文本来猜状态；同一 builder 必须接受候选未声明和已声明两种阶段，并可重复执行。

> 请把 MacroLens 任务治理拆成 schema、state machine、Git evidence、online receipt 四层。先定义结构化 task card/receipt/report/summary 模型和唯一状态迁移；再写一个按任务卡动态解析任意连续 source candidates 的 Git fixture builder，分别验证未集成、首次集成、重复集成零变更、REVIEW 和最终 summary。source commit 只能来自任务卡声明，同步 merge 不进入映射；集成后以 patch-id 保存 source→main SHA。最后接入真实部门线程回执，若目标线程三次系统失败则写 BLOCKED 报告并停止。完整运行所有正负测试后才允许修改 main。

## 恢复检查清单

- 获得集成发布部 remediation-10 的真实 RESERVED 回执。
- 审查并只集成任务卡列出的 11 个 direct source commits；排除所有同步 merge。
- 更新集成报告并登记 11 组 source→integrated SHA、Integration commit 和 Integration report commit。
- 派发测试部，运行 96 项组织测试及仓库检查。
- 全绿后把任务从 REVIEW 收口为 SUCCEEDED，并更新本 summary。
