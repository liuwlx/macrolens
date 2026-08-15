# ML-20260816-008 集成发布部报告

席位状态：`RUNNING`。阶段 01 已完成候选冻结核验；阶段 02 待完成分支推送、PR、GitHub CI、merge commit 与候选标签；阶段 03 为 `PENDING`，本席位不部署服务器、不操作本地 Docker，也不执行 migration、seed、sync 或任何运行态数据写入。

## 1. 问题与场景

本任务承接四源真实验收阻塞，需要把数据源部在基线 `97f20a839f4b53ca0b8bdd58d777682cd8d25954` 上形成的候选提交 `cb25253` 与 remediation 提交 `70badf6` 安全整合到 `master`。候选修复覆盖 BEA Decimal 单位缩放、BLS 精确日期与官方脚注绑定、EIA legacy `seriesid` 历史边界及本地 cutoff、Census EITS 完整维度过滤与固定 registry identity。

本轮只负责阶段 01/02 的冻结审查与 GitHub 发布链路。合并和打标签不代表四源已经完成生产运行态验收；后续仍须在阶段 03 通过既有 Admin MappingProbe/approval 形成真实血缘，再执行显式四源只读 `audit-live`。Scheduler 不在本任务修改范围内。

## 2. 分析过程

在指定独立 worktree 中重新核对分支、基线、提交图、差异文件和工作区状态。刷新远端引用后，`origin/master` 仍为 `97f20a839f4b53ca0b8bdd58d777682cd8d25954`，分支相对基线仅包含 `cb25253`、`70badf6`，工作区唯一未跟踪文件为本任务 `task-card.md`。差异未命中 migration、Alembic、Scheduler、OpenAPI 或 SDK 路径，`git diff --check` 通过；未发现既有同源 PR，现有候选标签只有 `v2026.08.16-rc.1`。

实现报告和双轴复核证据表明，首轮候选仍有 BEA 量级与 BLS 缺值证据约束两项 Spec 阻断；`70badf6` 已用 `Decimal` 的 `0.001` 显式缩放和精确官方脚注映射收口。最终 Standards 审查为 0 项、Spec 审查为 0 项。由于任务卡明确禁止 migration、seed、sync、服务器写入和 Scheduler 变更，本轮不会用运行态操作代替尚待阶段 03 完成的真实验收。

## 3. 解决流程与阶段结果

阶段 01 已核验并冻结候选。沿用已验证的原始门禁证据：`ruff check backend` 通过；`mypy backend/src` 为 70 个源文件无问题；`pytest backend/tests` 为 254 passed、5 条既有 warning；Node `22.13.1` 下 Web lint 为 0 error、2 条既有 warning，Web test 为 35 passed，Web build 通过；`git diff --check` 通过；最终 Standards 0、Spec 0。候选未包含 migration 或公共 API/Schema 变更，也没有 Scheduler 修改。

阶段 02 将把任务卡与本报告作为独立 docs commit 提交，再推送 `codex/ML-20260816-008-four-source-fix` 并创建目标为 `master` 的 PR。PR 必须准确列明变更范围、排除项、门禁证据、运行态 MappingProbe/approval 前置条件和 Scheduler 不变。只有全部 GitHub CI 成功后才允许以 merge commit 合并；随后在已合并提交上创建唯一 annotated tag `v2026.08.16-rc.2`，若远端届时已存在则不覆盖并改用 `v2026.08.16-rc.3`。

阶段 03 为 `PENDING`。本轮不登录服务器、不部署、不启动或修改 Compose、不执行 migration/seed/sync/backfill、不审批映射、不运行四源 audit，也不重启或重建 Scheduler。

## 4. Agents、skills、tools 与文档

未调用子 Agent，未使用额外 skill。使用 PowerShell、Git、GitHub CLI、计划更新和 `apply_patch` 完成只读审查、文档生成及后续授权的阶段 02 操作；未使用浏览器、Docker、数据库客户端或服务器连接。

本轮完整读取指定 worktree 的根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、本任务 `task-card.md` 和 `department-data-sources-01.md`。由于候选基线不含新版治理目录，又从项目主工作区只读加载新版根 `AGENTS.md`、宪法索引、`01-local-development-and-freeze.md`、`02-pr-merge-and-release.md`、`03-server-deploy-and-acceptance.md`；执行阶段为 01 和 02，阶段 03 只用于确认禁止边界并保持 pending。

## 5. 可沉淀经验与边界

发布门禁应把“代码与静态 registry 已就绪”和“生产映射已经 probe/approved”分开表达。`mapping_status=READY` 只允许候选进入运行态验证，不能替代真实 Provider 响应、审批血缘或 `verified + primary` 状态。BEA 单位换算必须使用 Decimal 并让 scale 进入 mapping fingerprint；BLS 缺值豁免必须同时绑定 canonical 日期与精确官方脚注；兼容 API 的历史边界和矩阵 API 的唯一 identity 都要由真实响应证据闭环。

阶段 02 的安全收口模式是：冻结提交与测试证据可追溯，PR 排除项显式写明，CI 失败即停止在诊断，合并后标签只指向主分支 merge commit。数据库运行态动作、Scheduler 和服务器验收属于独立授权边界，不能因为 PR 全绿或标签已创建而默认获批。

## 6. 更好的初始提示词

> 作为 ML-20260816-008 集成发布席位，在指定 worktree 和 `origin/master=97f20a8` 上先核对候选提交、唯一未跟踪任务卡、部门报告及完整门禁证据。生成七节集成报告和独立 docs commit；PR 明确四源修复、零 migration/seed/sync、Scheduler 不变以及合并后仍需 Admin MappingProbe/approval。等待全部 GitHub CI，全绿才 merge commit 合并，并在 merge SHA 上创建不覆盖既有标签的 annotated RC tag。CI 失败只诊断，禁止服务器、本地 Docker 和运行态数据操作。

## 7. 一次解决的更优方案提示词

> 严格按开发宪法 01→02 执行 ML-20260816-008：完整读取治理文件、任务卡和部门报告；确认分支只含 `cb25253`、`70badf6` 且工作区仅有 `task-card.md`；复核 BEA Decimal scaling、BLS exact footnote、EIA/Census 修复及全门禁结果；先提交任务卡和七节发布报告，再 push 并创建到 `master` 的 PR。持续轮询所有 GitHub checks，任一失败立即输出失败 run/job/日志摘要并停止；全绿后用 merge commit 合并，刷新 `origin/master` 验证 merge SHA，在该 SHA 创建并 push 唯一 annotated `v2026.08.16-rc.2`，冲突时改 `rc.3`。最终返回 PR URL、CI run、merge SHA、tag 和 clean git 状态。全程禁止部署、Docker、migration、seed、sync、MappingProbe/approval、audit-live 和 Scheduler 操作，阶段 03 保持 pending。
