# ML-20260804-001 集成发布部 01 工作报告

- 席位状态：REVIEW
- 任务 ID：`ML-20260804-001`
- 来源主线程：`/root`
- 初始基线：`b5ab5ed3cb2eec553bba4c4bc878c3abec5d0da8`
- 修复集成基线：`ee68b4c1e3fcac14b9b3cbf43b80e447639dbb8a`
- 初始后端候选：`e04464a91619c1bd107bb42c428a03ac2535a7c5` → main `62a9d5626ffc10e74baa77e9af992e74dc1f3e11`
- 初始前端候选：`a8b5a9099de41948c3a2e8e95c5b2dc8788e47e1` → main `2e3484981c0696e960ec3b27cb78464454830b1c`
- 后端修复候选：`dd2f147d1a309fd419af5b473c7a4e3e2acbb5e0` → main `d53c11589b185205624b753a112b80df6610a3ae`
- 桌面视觉修复候选：`6b5fbbfa801e5f082ff047927edb456c9a53f542` → main `36f535b56a42001e6ee09b9a6a4f9c47d053c5a4`
- 移动端与缓存修复候选：`aeb2dfca692b57715184dc76b1f991763bad0199` → main `2acf33adefbe2fd3868b8df93301edfded92a4f0`
- 完成结果：候选已按后端、桌面视觉、移动端与缓存顺序集成；唯一的 AI 页面冲突已合并两侧契约；验证通过。未推送、未部署、未切换生产 feature flag。

## 1. 问题与场景

数据浏览器的首轮全栈实现已经落到 main，但 Quality 复核后产生三组修复候选：后端补齐部署阻断项，前端修正桌面高度，另一前端候选修正移动端表格和跨账户缓存隔离。后端与移动端候选都修改 `apps/web/app/(app)/ai/page.tsx`，且分别承载必须同时保留的契约：创建 AI run 时发送 `Idempotency-Key`，以及 React Query 使用用户身份分区的 key 和失效范围。

共享 main 工作区还包含任务卡、设计文档、安全报告和设计 QA mock 等未跟踪资产。后端候选另带同路径任务卡，因此集成时必须避免覆盖或误提交主线程资产。

## 2. 分析过程

集成前核对了 main 基线、候选父提交、候选文件范围和提交级 `git diff --check`。后端候选中的任务卡与主线程未跟踪任务卡同路径但内容不同，因此先对主线程文件计算 SHA-256 并备份，cherry-pick 后从候选提交中移除该文件，再原样恢复主线程版本；恢复后哈希仍为 `24F244C9F8E06A95AB1A294158C0B3EEEE5511138E4382E0709E93240928705E`。

前两次 cherry-pick 完成后，第三个候选只在 AI 页面产生冲突。冲突不是二选一：创建 mutation 保留 `headers: { "Idempotency-Key": crypto.randomUUID() }`；AI runs、citations、saved views 和 notes 的 query key 保留 `userIdentity`；创建和取消成功后均失效当前用户的 `aiRunsKey`；身份变化时保留 `queryClient.clear()`。随后扫描确认没有残余冲突标记。

验证使用隔离的 Node 24 和现有完整 Python 3.12 虚拟环境，避免修改全局运行时。Next 构建自动改写的 `tsconfig.json` 与生成的 `next-env.d.ts` 均按候选范围之外的构建副作用清理。

## 3. 解决流程

1. 读取组织规则、任务卡和既有集成/质量材料，确认任务边界和候选顺序。
2. 记录 main 状态与五项需要保留的未跟踪资产，验证三个候选的父提交、范围和 whitespace。
3. 哈希备份主线程任务卡，cherry-pick 后端修复，移除候选自带任务卡并恢复主线程原文件，生成 `d53c115`。
4. cherry-pick 桌面视觉修复，生成 `36f535b`。
5. cherry-pick 移动端与缓存修复，手工合并 AI 页面冲突并生成 `2acf33a`。
6. 运行后端 16 项定向测试、Python compileall、Web typecheck/test/build、SDK typecheck 和差异检查。
7. 清理 Next 构建副作用，复核任务卡哈希、未跟踪资产、冲突标记和工作区范围。
8. 仅更新并提交本报告；不推送、不部署、不切换 feature flag。

## 4. Agents、Skills、Tools 与文档

- Agents：Engineering-01/02 提供初始候选，Quality 提供修复结论及候选协调，Integration & Release-01 完成 main 集成、冲突处理和门禁。此次未创建子 Agent。
- Skills：未使用专用 skill；工作属于既定 Git 集成、冲突解析和验证流程。
- Tools：`exec_command` 用于 Git、Node、Python、测试和哈希核验；`apply_patch` 用于冲突解析、清理构建副作用和维护报告；协作消息用于接收候选 SHA 与向主线程回传状态。
- 已读文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、任务卡、完整实现计划、UI 字符图复核、既有 Integration/Quality/Security 与 Engineering 部门报告，以及候选涉及的 API、schema、SDK、Web query 和页面代码。

## 5. 值得沉淀的经验与模式

1. 同路径未跟踪资产会被 cherry-pick 中的 tracked 文件覆盖；应在集成前记录哈希并做路径级备份，恢复后再次校验哈希。
2. 冲突解决应按行为契约合并，而不是按“ours/theirs”选边。幂等请求头和用户隔离缓存属于正交要求，必须同时保留并由测试或静态检查覆盖。
3. 候选提交到 main 的 SHA 会因冲突解决或移除越界文件而变化，报告应记录 candidate → main 的可追溯映射。
4. Web 构建成功后仍需复查工作区；Next 可能自动改写 TypeScript 配置并生成文件。
5. 验证运行时应隔离且固定版本，既保证可复现，也避免影响共享工作区中的其他席位。

## 6. 更好的初始提示词

> 请把数据浏览器的三个修复提交按“后端、桌面视觉、移动端与缓存”顺序集成到当前 main。开始前列出并保护工作区所有未提交和未跟踪文件；若候选包含同路径任务卡，先做哈希备份，集成时不要把候选任务卡带入 main，恢复后校验文件哈希。AI 页面冲突必须同时保留创建请求的 `Idempotency-Key`、按当前用户分区的 React Query keys、对应的精确失效范围和切换身份时清空缓存。完成后用 Node 24 运行 Web 17 项测试、typecheck、production build 和 SDK typecheck，用 Python 3.12 运行 `test_data_browser.py` 全部 16 项及 compileall；检查冲突标记、`git diff --check` 和构建副作用。只提交代码与集成报告，不推送、不部署、不切换 feature flag。

## 7. 当前方案反思与更优方案提示词

当前手工冲突解析正确，但更优方案是在候选交付前增加自动化契约测试：对 AI run 创建请求断言幂等键，对每类用户数据断言 query key 包含 identity，并模拟身份切换验证旧账户缓存不可见；同时由候选生成 manifest，声明预期文件范围和禁止携带的任务文档。这样集成人员只需验证 manifest 与自动化门禁，减少依赖人工阅读冲突块。

> 请为这次数据浏览器修复建立可复现的集成门禁：每个候选附带父 SHA、预期文件清单和禁止覆盖路径；流水线在临时分支按指定顺序 cherry-pick，并自动保护主线程未跟踪文件。增加 AI 创建幂等键、用户级 query key、精确 invalidation 和账户切换缓存清空测试；随后在固定 Node 24/Python 3.12 环境运行 Web、SDK、后端定向门禁，检测 Next 构建副作用、冲突标记和越界文件。全部通过后生成 candidate→main SHA 映射与报告，但不自动推送、部署或切换生产 flag。

## 检查结果、风险与交接

- 三个修复候选提交级 `git diff --check`：通过。
- `git diff ee68b4c...HEAD --check` 与工作区 `git diff --check`：通过。
- 冲突标记扫描：`apps`、`backend`、`packages` 均无残留。
- Node `v24.18.1` Web typecheck：通过。
- Node `v24.18.1` Web test：8 个文件、17 项测试全部通过。
- Node `v24.18.1` Web production build：通过，15 个路由生成成功（含 `/data`）。
- Node `v24.18.1` SDK typecheck：通过。
- Python 3.12 compileall（`backend/src`、`backend/tests`）：通过。
- `pytest backend/tests/test_data_browser.py -q`：16 项全部通过（0 skipped）。
- 尚未执行本轮全量 ruff、mypy、全量 pytest、Web lint、E2E 和运行态视觉 QA；仍应由 Quality/Security 或后续完整发布环境继续门控。
- 主线程五项既有未跟踪资产保持未跟踪：`artifacts/design-qa/mock-api.mjs`、两份设计文档、Security 报告和任务卡；本报告提交不会纳入这些文件。
- 本轮没有 push、服务器部署、外部状态变更或生产 feature flag 切换。
