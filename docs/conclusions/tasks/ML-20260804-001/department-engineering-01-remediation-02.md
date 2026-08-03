# ML-20260804-001 / Engineering-01 Remediation 02 工作报告

## 1. 问题与场景

本次只处理两个新 P1。第一，legacy `get_primary_source` 使用 `.first()`，当同一指标存在多个 verified primary 映射时会静默选择一个来源；没有映射和映射冲突没有被可靠区分。第二，浏览器的 `current_period`、`current`、`change`、`period_change`、`yoy` 在元数据分页后才对页内数据排序，导致全局最大项可能永远不会进入第一页；但若恢复为给所有候选加载 420 点，又会重新引入性能问题。

## 2. 分析过程

先追踪 observations/revisions 到 `get_primary_source` 的共同调用链，确认在来源解析阶段 fail closed 即可同时保护两个接口。随后对照 `build_browser_item` 和 `transform_points` 的计算语义，确定动态排序只需要当前值、直接前值、期间变化基期和同比基期。daily/weekly 的期间变化沿用直接前一观测，同比日历目标保留 7/14 天容差。最后检查许可语义，确认全局排序指标也必须先经过严格 display 许可，避免被拒绝的数值影响排序。

## 3. 解决流程

1. `get_primary_source` 查询最多两条 verified primary：零条返回 `source_mapping_not_ready`，多条返回 409 `source_mapping_conflict`，仅一条时返回映射。
2. 新增批量窄窗口查询 `_sort_points_by_source`：数据库先按 `data_as_of` 选择每期最新 vintage，再只返回每个来源当前/前值，以及所需的 1、3、12 个月日历目标窗口；daily/weekly 只对 12 个月同比目标分别使用 7/14 天容差。
3. 动态排序前批量解析全部匹配来源的严格许可，用窄窗口点构造与页面一致的五种排序值。
4. 先按 taxonomy order、名称、code、UUID 建立稳定 tie-break，再按动态值全局稳定排序；缺失值稳定放在末尾。完成全局 offset/limit 后，才为页内来源加载最多 420 点完整展示数据。
5. 添加 observations/revisions 的零/多主源参数化测试，五种动态排序的跨页 top-N 参数化测试，以及 PostgreSQL dialect 下 daily/weekly 窄窗口 SQL 编译测试。

## 4. Agents、skills、tools 与文档

- Agent：仅 `engineering-01`，未创建子 Agent。
- Skills：未使用额外 skill。
- Tools：`exec_command` 用于检索、测试和 Git 检查；`apply_patch` 用于代码与报告修改；协作消息工具用于主线程状态同步；`update_plan` 用于维护执行进度。
- 阅读文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260804-001/task-card.md`、根目录注入的 `AGENTS.md` 规则。

## 5. 值得沉淀的经验与模式

- 唯一业务映射不能通过 `.first()` 消解冲突；查询两条即可低成本区分零、一、多三种状态并 fail closed。
- “全局排序”和“页内昂贵加载”并不冲突：可先用批量窄窗口/summary 查询构造全局 sort key，再对选中页加载完整展示历史。
- 排序摘要必须复用页面的许可与计算语义，否则会发生隐藏数值泄漏或排序/展示不一致。
- 动态值相同和缺失值都需要独立的稳定 tie-break，UUID 应作为最终确定性键。
- 时间窗口 SQL 应至少用目标生产数据库 dialect 编译测试，避免 mock 或 SQLite 测试掩盖 interval 表达式问题。

## 6. 更好的初始提示词

“请修复 MacroLens 两个后端 P1：`get_primary_source` 必须区分零、一、多 verified primary，零条让 observations/revisions 返回 not-ready，多条返回 409 `source_mapping_conflict`；浏览器的 current_period/current/change/period_change/yoy 必须在分页前全局排序，但不得为所有候选加载 420 点。请用批量窄窗口查询计算排序摘要，复用严格许可和现有 transform 语义，使用 taxonomy/name/code/UUID 稳定 tie-break，分页后只加载页内完整历史，并补跨页、冲突及 PostgreSQL SQL 编译测试。”

## 7. 更优方案反思与一次解决提示词

当前方案以单个批量窗口查询兼顾正确性和上线改动范围。长期更优方案是维护按 source、vintage cutoff 生成的浏览器指标摘要表或增量物化视图，使五种全局排序直接走索引，并用数据更新事务同步失效；这会需要迁移、刷新策略和数据平台验收，不适合本次冻结范围。

一次解决提示词：

“为 MacroLens 设计并实现可索引的 browser metric snapshot：每个 source/vintage 保存 current_period、current、change、period_change、yoy 与许可可见性，观测入库时事务性刷新；所有动态排序先在 snapshot 上做全局排序和分页，再加载页内历史。与此同时把唯一主源解析抽成统一 resolver，零/多映射 fail closed。提供迁移、回填、并发一致性测试、五种跨页排序契约测试和查询计划基准，完成门禁、报告与独立提交。”

## 检查结果与风险

- `pytest backend/tests/test_data_browser.py -q`：26 passed。
- `ruff check`：`data_browser.py` 与聚焦测试完整通过；`series.py --select F` 通过（该文件仍有基线 E501）。
- 聚焦 mypy：2 个变更源文件通过。
- `python -m compileall -q backend/src backend/tests`：通过。
- `npm --workspace packages/sdk-typescript run typecheck`：通过。
- `git diff --check`：通过。
- 风险：窄窗口 SQL 使用 PostgreSQL interval/date 运算，已用 PostgreSQL dialect 编译验证，但当前环境未连接真实 PostgreSQL 执行；建议 Integration/Release 做一次带真实 vintage 数据的查询验收。
