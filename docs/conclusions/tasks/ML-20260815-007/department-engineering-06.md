# ML-20260815-007｜FOMC 验收夹具选择修复

## 1. 问题与场景

提交 `76d9449` 的 GitHub run `31893699218` 中，backend、frontend、containers 通过，Chromium acceptance 17/18 通过。唯一失败是 FOMC detail 的 `projections` 为空；AI、序列修订和参数转发修复均已生效。

## 2. 分析过程

日志显示 E2E 调用 `/fomc/meetings?limit=100` 后直接选 `items[0]`。生产接口按会议日期倒序，catalog seed 含比 acceptance fixture 更新、但无 projections 的会议。代码核对确认 acceptance fixture 日期 `2026-07-28` 的会议已创建 projections、dots 和 probabilities，因此问题不是写入失败，而是测试依赖了未承诺的“第一个就是 fixture”排序前提。

## 3. 解决流程

将 critical-path E2E 改为在会议列表中按 fixture 的稳定 `meeting_start=2026-07-28` 选择目标，先断言目标存在，再对同一 ID 验证 projections、dots 和 probabilities。未改变 FOMC 生产排序，未给其他目录会议伪造数据。复跑六门禁：ruff 通过；mypy 70 文件通过；pytest 242 项通过；Web lint 0 error/2 既有 warning；Web test 35 项通过；Web build 通过。

## 4. Agents、skills、tools 与文档

- Agent：主线程独立完成；未新增子 Agent。
- Skill：继续使用 `diagnosing-bugs` 的“固定失败—首错—证伪—最小修复—复验”反馈环。
- Tools：GitHub CLI 读取失败 job 日志；PowerShell/rg 只读检查；`apply_patch` 修改；Python 3.12 与 Node 22.14.0 执行门禁。
- 文档：本任务已加载的 `AGENTS.md`、组织规则、开发宪法 README 和阶段 01/02/03；任务卡；run `31893699218` 日志；FOMC router、fixture 和 E2E。
- 阶段：阶段 01 修复与冻结；阶段 02 等待新提交 CI；未进入阶段 03。

## 5. 值得沉淀的经验或模式

验收测试应选择自己创建的实体，不得依赖和 catalog seed 混合后的列表首项。稳定选择键应来自 fixture 的业务字段或显式返回 ID；生产排序不应为测试便利而改变。

## 6. 更好的初始提示词

> 检查 GitHub acceptance 的首个失败。如果 FOMC 列表有数据但 detail 缺 projections，先确认测试选中的会议是否真是 acceptance fixture；核对列表排序和 seed 中其他会议。让 E2E 用 fixture 的稳定业务字段选择目标，并对同一 ID 验证 projections、dots、probabilities；不要修改生产排序或给无投影会议伪造数据。复跑六门禁、提交并等待 CI；本地禁止容器。

## 7. 更优方案反思与提示词

按日期选择已消除当前不确定性。更优的长期方案是 seed-test-fixtures 输出机器可读 fixture manifest（包含 series、release、meeting、document ID），E2E 在 setup 阶段保存并消费，完全避免硬编码日期；这需要调整 CLI 与 CI 数据传递，本轮不扩大。

> 为运行时 acceptance 增加 fixture manifest：seed-test-fixtures 输出版本化 JSON，包含所有验收实体 ID 和能力；GitHub workflow 将其作为只读输入交给 Playwright，E2E 只按 manifest 访问，不从混合目录列表猜测首项。保持 test-only 双开关，补 CLI/schema/E2E 契约测试和六门禁，不改生产排序与数据。
