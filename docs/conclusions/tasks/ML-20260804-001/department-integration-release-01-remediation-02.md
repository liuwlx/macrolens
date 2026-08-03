# ML-20260804-001 / Integration & Release-01 Remediation 02 工作报告

- 席位状态：REVIEW
- 来源主线程：`/root`
- 集成基线：`69e643107821542fb2d753f2a17179b8067de8c8`
- Engineering 候选：`d19676ae87705e7d5e2a76a7a5c98a3b6a19081c`
- main 集成提交：`62fd1b9ee29691448dbe77cded681c0294b927aa`
- 结果：Remediation 02 已单独集成并通过定向门禁；未推送、未部署，尚不宣称完整 release pass。

## 1. 问题与场景

Quality 二次复核发现两个后端 P1。其一，legacy observations/revisions 路径通过 `.first()` 静默选择 verified primary source，无法区分零映射与多映射冲突。其二，浏览器的 `current_period`、`current`、`change`、`period_change`、`yoy` 排序发生在分页之后，导致跨页结果不是全局有序；若直接为全部候选加载 420 点历史，又会恢复已修复的性能问题。

候选提交还包含一份同路径的窄版任务卡，而 main 工作区持有完整、未跟踪的主任务卡。直接 cherry-pick 会覆盖主线程资产，因此集成必须同时保证代码提交范围和任务卡完整性。

## 2. 分析过程

先复读组织规则与完整主任务卡，核对当前 main、候选父提交、文件范围和提交级 whitespace。候选父提交为 `2acf33a`，当前 main 在其上只增加评审与集成报告，后端代码没有额外分叉。

代码审计确认候选将唯一主源解析改为最多读取两行，从而对零、一、多映射 fail closed；动态排序新增一个批量窄窗口查询，只提取所有匹配来源的当前、前值和月度/同比目标窗口，排序与分页完成后才为页内来源加载完整历史。许可计算、稳定 tie-break 和历史 `data_as_of` 继续沿用现有路径。

主任务卡在移出前后均计算 SHA-256。候选落地后从集成提交中移除窄版任务卡，再恢复原文件；最终哈希仍为 `24F244C9F8E06A95AB1A294158C0B3EEEE5511138E4382E0709E93240928705E`。

## 3. 解决流程

1. 读取 `.codex/organization.toml`、`docs/organization/README.md` 和完整主任务卡。
2. 核验 main=`69e6431`、候选=`d19676a`、候选父提交与提交级 `git diff --check`。
3. 哈希备份主任务卡，单独 cherry-pick 候选。
4. 从集成提交移除候选窄版任务卡并原样恢复完整任务卡，得到 main 提交 `62fd1b9`。
5. 审计最终差异，仅保留两个服务文件、聚焦测试和 Engineering Remediation 02 报告。
6. 运行 26 项 focused pytest、ruff、mypy、compileall、SDK typecheck 和 PostgreSQL dialect 编译测试。
7. 清理并发前端检查产生的 Next 配置副作用，执行最终 Git 范围与 whitespace 检查。
8. 单独提交本报告；不 push、不部署。

## 4. Agents、Skills、Tools 与文档

- Agents：Engineering-01 提供 Remediation 02 候选；Quality-01 提供二次复核结论；Integration & Release-01 完成集成和门禁。本席位未创建子 Agent。
- Skills：未使用专用 skill；本任务属于组织规则已定义的 Git 集成与发布门禁。
- Tools：`exec_command` 用于 Git、Python、Node、测试、哈希和 Docker 状态核验；`apply_patch` 用于清理 Next 构建副作用与新增报告；`update_plan` 维护执行进度；协作消息用于与来源主线程和 Engineering 席位同步。
- 已读文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、主任务卡、Engineering Remediation 02 报告、既有 Integration/Quality 报告，以及候选涉及的服务与测试差异。

## 5. 值得沉淀的经验与模式

1. “全局排序”不要求“全量重历史加载”：用批量摘要/窄窗口生成 sort key，再对页内数据加载完整历史，可以同时保证正确性与性能。
2. 唯一映射不能通过 `.first()` 消解；读取上限两条即可低成本区分零、一、多三种业务状态。
3. 同路径未跟踪文档是 cherry-pick 的独立风险面。集成前后做哈希校验，并从候选提交排除窄版替代文件，可以保留主线程事实来源。
4. PostgreSQL 特有日期/interval SQL 至少应进行目标 dialect 编译测试；真正发布前仍应在真实 PostgreSQL 上执行带 vintage 数据的查询。
5. 聚焦 mypy 使用 `--follow-imports=skip` 时必须明确标注，因为它验证变更文件自身，但不等价于仓库级严格 mypy。

## 6. 更好的初始提示词

> 请在当前 main 上仅集成 Remediation 02 候选。先读取组织规则和完整主任务卡，并保护所有未跟踪文件；候选若带同路径窄版任务卡，先记录主任务卡 SHA-256，集成时排除候选任务卡并原样恢复。审计唯一主源必须对零/多映射 fail closed，五种动态指标必须在分页前全局稳定排序，同时只用批量窄窗口计算全量 sort key、分页后再加载页内 420 点。运行 `test_data_browser.py` 26 项、变更文件 ruff、聚焦 mypy、compileall、Node 24 SDK typecheck、PostgreSQL dialect 编译测试和 Git diff check；单独提交七节报告，不 push、不部署。

## 7. 当前方案反思与更优方案提示词

当前方案在冻结范围内正确且成本可控，但排序时仍需按请求计算全部匹配来源的窄窗口。长期更优方案是由数据平台维护具备 `data_as_of`/许可语义的版本化 browser metric snapshot，并为五种动态字段建立索引；API 可直接全局排序分页，页面详情仍读取 append-only vintage。该方案需要迁移、回填、刷新一致性和查询计划验收，不应混入本次修复。

> 请设计一个版本化、可索引的 browser metric snapshot：每个 source 和 snapshot cutoff 保存 current_period、current、change、period_change、yoy 与许可可见性，观测新 vintage 入库时事务性刷新或失效。浏览器先在 snapshot 上全局排序分页，再加载页内完整历史；唯一主源统一通过零/一/多 resolver。提供迁移与回填、并发一致性、许可变化、五种跨页排序、真实 PostgreSQL 查询计划和回滚测试，并保持旧路径 feature flag 可回退。

## 检查结果与 residual risk

- `pytest backend/tests/test_data_browser.py -q`：26 passed，0 skipped。
- PostgreSQL dialect 定向用例：`test_sort_window_query_compiles_daily_and_weekly_yoy_targets_only`，1 passed；验证 daily/weekly interval/date SQL 可由 PostgreSQL dialect 编译。
- ruff：`data_browser.py` 与 `test_data_browser.py` 全规则通过；`series.py --select F` 通过。`series.py` 全规则仍有 7 个既有 E501，候选未修改这些长行。
- mypy：两个变更源文件使用 `--follow-imports=skip` 通过。按仓库默认严格导入运行仍因当前 venv 缺少 `pgvector` 和既有 `schemas/models.py` 类型问题失败，不能据此宣称仓库级 mypy 通过。
- Python 3.12 compileall（`backend/src`、`backend/tests`）：通过。
- Node `v24.18.1` SDK typecheck：通过。
- 候选、集成范围和工作区 `git diff --check`：通过；最终范围无冲突标记。
- 当前没有运行中的 PostgreSQL 容器，因此未执行真实数据库查询；生产前仍需对多来源、跨页动态排序和 vintage cutoff 做真实 PostgreSQL 验收。
- 未执行本轮全量 pytest、Web 门禁、E2E 或视觉 QA；本提交只关闭两个后端 P1，不代表整个任务 release pass。
- 未 push、未部署、未切换 feature flag。
