# ML-20260804-001 集成发布部 01 工作报告

- 席位状态：REVIEW
- 任务 ID：ML-20260804-001
- 来源主线程：`/root`
- 起始提交：`b5ab5ed3cb2eec553bba4c4bc878c3abec5d0da8`
- 后端候选：`e04464a91619c1bd107bb42c428a03ac2535a7c5`
- 前端候选：`a8b5a9099de41948c3a2e8e95c5b2dc8788e47e1`
- main 后端提交：`62a9d5626ffc10e74baa77e9af992e74dc1f3e11`
- main 前端提交：`2e3484981c0696e960ec3b27cb78464454830b1c`
- 完成结果：严格按后端、前端顺序完成无冲突 cherry-pick，复核 API/SDK/Web 合同，并执行当前环境可用的集成门禁；未推送、未部署、未切换生产 feature flag。

## 1. 问题与场景

本任务由两个从同一基线并行开发的候选组成：后端新增数据浏览、快照、导出、分析、AI capability 和 TypeScript SDK 合同；前端重建 `/data`，并消费这些新合同。集成风险集中在并行提交顺序、API/SDK 字段漂移、Next 构建期 feature flag、许可与 `data_as_of` 语义，以及共享主工作区中三个未跟踪任务文档不能丢失或被误提交。

## 2. 分析过程

集成前确认两个候选父提交均为任务基线，并分别审查文件清单和 `git diff --check`。后端先落地主 API、Pydantic schema 和 SDK；前端随后落地，因此没有让前端分支中的本地类型覆盖后端权威合同。两个 cherry-pick 都没有文本冲突，主分支三个未跟踪任务文档始终保留。

集成后静态对照 taxonomy children、series browser/export/analytics、AI capabilities 的后端路由、Pydantic 返回模型、SDK 方法与 Web 请求路径。Web 和 SDK 在 Node 24 下通过类型检查，证明 TypeScript 侧不存在集成后签名断裂；前端单测与 production build 也通过。Python 3.12 compileall 通过。当前可用 pytest 环境为 Python 3.11 且缺少 `pytest-asyncio`，所以 data-browser 定向结果为 3 passed、3 skipped；被跳过的正是异步安全边界测试，不能宣称完整后端定向门禁通过。

## 3. 解决流程

1. 完整读取组织规则、任务卡和两个研发部门报告，确认顺序与修改边界。
2. 记录 main 基线、三个未跟踪任务文档和两个候选的完整 SHA、父提交、文件范围。
3. 对两个候选分别运行提交级 whitespace 检查。
4. 先 cherry-pick 后端候选，生成 main 提交 `62a9d5626ffc10e74baa77e9af992e74dc1f3e11`。
5. 再 cherry-pick 前端候选，生成 main 提交 `2e3484981c0696e960ec3b27cb78464454830b1c`；没有产生冲突。
6. 使用隔离的 Node `v24.18.1` 运行 Web typecheck、6 文件 15 测试、SDK typecheck 和 Web production build。
7. 清理 Next build 自动生成的 `next-env.d.ts` 和对 `tsconfig.json` 的非候选改写。
8. 运行 Python 3.12 compileall、可用 pytest 定向测试、集成范围与工作区 `git diff --check`。
9. 静态复核 API、Pydantic、SDK 与 Web 的路由、查询参数、响应字段、快照和许可动作对应关系。
10. 仅新增本集成报告提交；不纳入主线程持有的三个未跟踪任务文档。

## 4. Agents、Skills、Tools 与文档

- Agents：Engineering-01 提供后端候选；Engineering-02 提供前端候选；Integration & Release-01 完成 main 集成和门禁。未创建子 Agent。
- Skills：本席位未使用专用 skill；工作性质为 Git 集成、合同复核和发布门禁。
- Tools：`exec_command` 用于 Git、Node、Python、测试和合同检索；`apply_patch` 用于清理构建副作用并编写本报告；协作消息用于接收候选 SHA 和回传状态。
- 已读文档：`.codex/organization.toml`、`docs/organization/README.md`、根 `AGENTS.md`、任务卡、完整实现计划、字符图复核文档、`department-engineering-01.md`、`department-engineering-02.md`，以及本次涉及的路由、schema、SDK、Web API/types 和数据浏览器组件。

## 5. 值得沉淀的经验与模式

1. 并行全栈候选应从同一冻结基线出发，并让后端权威合同先落地；这样前端冲突只需围绕真实 API/SDK 解决。
2. `git cherry-pick` 无文本冲突不等于合同无冲突，仍需同时对照路由、查询参数、Pydantic、SDK 和 Web 请求。
3. Node 版本门禁应使用隔离运行时，避免切换全局 NVM 影响其他并行席位。
4. Next build 会产生工作区副作用；绿色构建后必须再次审计状态并清理非候选文件。
5. pytest 的退出码 0 不能掩盖 skipped 安全测试；缺插件时必须单独报告通过数与跳过数。
6. 未跟踪任务文档应在集成前建立保留清单，并使用精确路径暂存报告，避免 `git add .` 混入主线程资产。

## 6. 更好的初始提示词

> 请集成同一基线产生的 MacroLens 数据浏览器后端和前端候选。先记录 main 的 tracked、staged、untracked 状态并保留所有主线程任务文档；验证两个候选父提交和文件范围，分别运行 commit diff check。严格先 cherry-pick 后端 API/Pydantic/SDK，再 cherry-pick 前端；即使无文本冲突，也要逐项核对 taxonomy children、series browser/export/analytics、AI capabilities 的路由、参数、响应字段、`data_as_of` 和许可动作。使用隔离 Node 24 运行 Web typecheck/test/build 与 SDK typecheck，使用 Python 3.12 compileall 和具备 async 插件的 pytest 环境运行 data-browser 定向测试。清理 Next 构建副作用，只提交集成报告，不推送、不部署、不切换生产 flag。

## 7. 当前方案反思与更优方案提示词

更优方案是在候选交付前由后端生成 OpenAPI/SDK，并让前端候选直接基于该产物开发；集成环境使用锁定的 Node 24 与完整 Python 3.12 测试镜像，再以固定认证 fixture 运行 API 合同、E2E 和视觉 QA。这样可以把静态人工合同对照升级为自动化差异门禁，并避免本机 Python 插件缺失导致异步测试跳过。

> 请建立一个可复现的 MacroLens 全栈集成流水线：后端候选先生成并校验 OpenAPI 与 TypeScript SDK，前端只依赖该版本；合并后在固定 Node 24、Python 3.12、PostgreSQL/pgvector 和 MinIO 环境中运行 schema/OpenAPI diff、完整 data-browser 异步测试、Web typecheck/test/build、SDK typecheck、认证 E2E 和五视口截图比较。任何 skipped 安全测试、合同漂移或 `design-qa.md` 非 passed 都阻断交付；流水线只输出可追溯提交、检查日志和回滚说明，不自动切换生产 flag。

## 检查结果、风险与交接

- 两个候选提交级 `git diff --check`：通过。
- 集成范围 `git diff b5ab5ed..HEAD --check`：通过。
- 工作区 `git diff --check`：通过。
- Node `v24.18.1` Web typecheck：通过。
- Node `v24.18.1` Web test：6 个文件、15 个测试通过。
- Node `v24.18.1` Web production build：通过，`/data` 静态路由生成成功。
- Node `v24.18.1` SDK typecheck：通过。
- Python 3.12 compileall（backend/src、backend/tests）：通过。
- `pytest backend/tests/test_data_browser.py -q`：3 passed、3 skipped；本机 Python 3.11 环境缺少 `pytest-asyncio`，异步许可/快照/贡献安全测试尚需在完整 Python 3.12 环境重跑。
- 未执行：全量 ruff、mypy、全量 pytest、Web lint、E2E、运行态后端合同和视觉截图；按任务卡应由 Security、Quality 与后续完整集成环境继续门控。
- 根 `design-qa.md` 尚未由 Quality 生成 `final result: passed`，因此本报告不宣称整项任务完成。
- 主分支三个任务文档仍为未跟踪状态，未纳入任何 cherry-pick 或本报告暂存。
