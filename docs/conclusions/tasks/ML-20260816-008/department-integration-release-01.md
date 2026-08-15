# ML-20260816-008 集成发布部报告

席位状态：`RUNNING`。首轮阶段 02 已通过 PR #12 合并并发布 `v2026.08.16-rc.2`；当前对追加候选 `f468736` 执行 follow-up 阶段 02。阶段 03 仍为 `PENDING`，本席位不部署服务器、不操作本地 Docker，也不执行 migration、seed、sync 或任何运行态数据写入。

## 1. 问题与场景

本任务承接四源真实验收阻塞，需要把数据源部在基线 `97f20a839f4b53ca0b8bdd58d777682cd8d25954` 上形成的候选提交 `cb25253` 与 remediation 提交 `70badf6` 安全整合到 `master`。候选修复覆盖 BEA Decimal 单位缩放、BLS 精确日期与官方脚注绑定、EIA legacy `seriesid` 历史边界及本地 cutoff、Census EITS 完整维度过滤与固定 registry identity。

本轮只负责阶段 01/02 的冻结审查与 GitHub 发布链路。合并和打标签不代表四源已经完成生产运行态验收；后续仍须在阶段 03 通过既有 Admin MappingProbe/approval 形成真实血缘，再执行显式四源只读 `audit-live`。Scheduler 不在本任务修改范围内。

首轮合并后发现 Census EITS 的 `time` 既被放入 `get` 字段列表，又作为独立查询参数发送；真实接口要求 `time` 只作为查询参数。追加候选 `f468736` 在 probe/fetch 两条路径从 `get` 中排除 `time`，保留独立 `time` 参数和 `time_slot_date` 取数，并补充契约断言。本 follow-up 只整合该修复与本报告，不修改其他产品代码。

## 2. 分析过程

在指定独立 worktree 中重新核对分支、基线、提交图、差异文件和工作区状态。刷新远端引用后，`origin/master` 仍为 `97f20a839f4b53ca0b8bdd58d777682cd8d25954`，分支相对基线仅包含 `cb25253`、`70badf6`，工作区唯一未跟踪文件为本任务 `task-card.md`。差异未命中 migration、Alembic、Scheduler、OpenAPI 或 SDK 路径，`git diff --check` 通过；未发现既有同源 PR，现有候选标签只有 `v2026.08.16-rc.1`。

实现报告和双轴复核证据表明，首轮候选仍有 BEA 量级与 BLS 缺值证据约束两项 Spec 阻断；`70badf6` 已用 `Decimal` 的 `0.001` 显式缩放和精确官方脚注映射收口。最终 Standards 审查为 0 项、Spec 审查为 0 项。由于任务卡明确禁止 migration、seed、sync、服务器写入和 Scheduler 变更，本轮不会用运行态操作代替尚待阶段 03 完成的真实验收。

follow-up 开始时工作区 clean，`HEAD=f46873674f12f1cc8d6be02a9eeec145a5362be2`，`origin/master=16e07d6f7b5ce840ea93508f80e64f48a35bf7d7`，merge-base 为首轮 docs commit `cee977b`。三点比较证明 follow-up 相对已合并主线仅修改 `backend/src/macrolens_worker/providers/census.py` 与 `backend/tests/test_mapping_probes.py`；`git diff --check` 通过，未发现同源 open PR，远端已有 `rc.1/rc.2` 且 `rc.3` 尚不存在。追加候选的 Standards/Spec 复审均为 0 findings。

## 3. 解决流程与阶段结果

阶段 01 已核验并冻结候选。沿用已验证的原始门禁证据：`ruff check backend` 通过；`mypy backend/src` 为 70 个源文件无问题；`pytest backend/tests` 为 254 passed、5 条既有 warning；Node `22.13.1` 下 Web lint 为 0 error、2 条既有 warning，Web test 为 35 passed，Web build 通过；`git diff --check` 通过；最终 Standards 0、Spec 0。候选未包含 migration 或公共 API/Schema 变更，也没有 Scheduler 修改。

首轮阶段 02 已完成：PR #12 全部 GitHub CI 成功后以 merge commit `16e07d6f7b5ce840ea93508f80e64f48a35bf7d7` 合并，annotated tag `v2026.08.16-rc.2` 指向该提交。

follow-up 阶段 01 证据已由来源席位提供并经集成席位核对候选边界：`ruff check backend` 通过；`mypy backend/src` 为 70 个源文件无问题；`pytest backend/tests` 为 254 passed；Web lint 为 0 error、2 条既有 warning，Web test 为 35 passed，Web build 通过；Standards 0、Spec 0。下一步仅提交本报告、推送分支、创建目标为 `master` 的 follow-up PR，等待全部 GitHub 必需检查成功后以 merge commit 合并，并在精确的主线 merge SHA 上创建 annotated tag `v2026.08.16-rc.3`。

阶段 03 为 `PENDING`。本轮不登录服务器、不部署、不启动或修改 Compose、不执行 migration/seed/sync/backfill、不审批映射、不运行四源 audit，也不重启或重建 Scheduler。

## 4. Agents、skills、tools 与文档

未调用子 Agent，未使用额外 skill。使用 PowerShell、Git、GitHub CLI、计划更新和 `apply_patch` 完成只读审查、文档生成及后续授权的阶段 02 操作；未使用浏览器、Docker、数据库客户端或服务器连接。

本轮完整读取指定 worktree 的根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、本任务 `task-card.md` 和 `department-data-sources-01.md`。由于候选基线不含新版治理目录，又从项目主工作区只读加载新版根 `AGENTS.md`、宪法索引、`01-local-development-and-freeze.md`、`02-pr-merge-and-release.md`、`03-server-deploy-and-acceptance.md`；执行阶段为 01 和 02，阶段 03 只用于确认禁止边界并保持 pending。

follow-up 轮次未调用子 Agent、未使用额外 skill。重新读取 worktree 与主工作区根 `AGENTS.md`、组织配置/README、治理索引、阶段 01/02/03 宪法、任务卡和本报告；阶段 01 仅核对已冻结证据，执行阶段仍为 02，阶段 03 仅确认禁止部署边界。工具仍限于 PowerShell、Git、GitHub CLI、计划更新与 `apply_patch`。

## 5. 可沉淀经验与边界

发布门禁应把“代码与静态 registry 已就绪”和“生产映射已经 probe/approved”分开表达。`mapping_status=READY` 只允许候选进入运行态验证，不能替代真实 Provider 响应、审批血缘或 `verified + primary` 状态。BEA 单位换算必须使用 Decimal 并让 scale 进入 mapping fingerprint；BLS 缺值豁免必须同时绑定 canonical 日期与精确官方脚注；兼容 API 的历史边界和矩阵 API 的唯一 identity 都要由真实响应证据闭环。

阶段 02 的安全收口模式是：冻结提交与测试证据可追溯，PR 排除项显式写明，CI 失败即停止在诊断，合并后标签只指向主分支 merge commit。数据库运行态动作、Scheduler 和服务器验收属于独立授权边界，不能因为 PR 全绿或标签已创建而默认获批。

Census 参数契约还应区分“响应字段”与“查询维度”：`time` 可以作为独立查询参数并由上游返回，但不能重复放入 `get`。构造字段列表时应在去重后显式排除保留查询参数，并用 probe/fetch 两条公开 seam 同时断言，避免 mock 只验证业务值却漏掉真实 URL 契约。

## 6. 更好的初始提示词

> 继续 ML-20260816-008 阶段 02：在指定 worktree 核对 `f468736` 相对已合并 PR #12 的差异只包含 Census `get` 参数修复及对应测试，确认 worktree clean 和完整门禁证据；仅更新既有 integration-release 报告并提交。推送原分支、创建到 `master` 的 follow-up PR，等待所有必需 CI，全绿后 merge commit 合并，并在精确 merge SHA 上创建 annotated `v2026.08.16-rc.3`。禁止产品代码追加修改、服务器部署、migration、seed 和 sync。

## 7. 一次解决的更优方案提示词

> 严格执行 ML-20260816-008 follow-up 发布：重读组织规则与 01/02/03 宪法，先证明 worktree clean、`HEAD=f468736`、`origin/master` 为 PR #12 merge SHA、三点 diff 只有 Census adapter/test，且 `rc.3` 不存在。沿用已给出的六项本地门禁与双轴 0 findings，只允许修改并提交现有 integration-release 报告。push 后创建 follow-up PR，正文记录 Census `time` 只作查询参数、不进入 `get`，以及无 Schema/API/migration/seed/sync/部署影响。持续轮询全部 PR checks；失败只诊断，全绿才 merge commit。fetch 后要求 `origin/master` 精确等于 GitHub merge SHA，再创建、验证并 push annotated `v2026.08.16-rc.3`；确认 tag peeled SHA、无 tag 触发部署、最终工作区 clean。阶段 03、Admin MappingProbe/approval、audit-live 与 Scheduler 操作全部保持 pending。
