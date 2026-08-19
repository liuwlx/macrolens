# ML-20260820-050｜TradingView 非连续历史质量策略修复

## 1. 问题与场景

用户提供的生产证据显示，批次 `e9aed49a-a9aa-4aab-bde9-6f0ad9f09199` 中 74 个唯一失败全部为 `history_gap`：monthly 46、weekly 21、annual 4、quarterly 3、daily 0。TradingView chart 已发出 `series_completed`，实际历史点已抓取，但完整性检查把存在非连续历史的整条序列作为 blocking issue，导致 ingestion run 被 quarantine。

以上批次统计和 TradingView 运行状态来自任务卡，本次没有连接生产数据库重复查询。经本地代码核实，原 severity 策略只把 `TRADINGVIEW_WEB` 的 `ECONOMICS:USUR` 在 2025-10-01 的单个缺口降级为 warning，无法覆盖生产证据中的通用低频非连续历史场景。

## 2. 分析过程

1. 核对 `origin/master` 与任务基线，二者均为 `564c3df2df26bbdcf998bcccc76839bce9587605`。
2. 检查主工作区，发现存在大量他人未提交改动，因此从指定基线创建独立 worktree 和分支，未触碰或回滚主工作区内容。
3. 阅读完整性检查后确认：`history_gap` 已计算缺口数量、首个缺口和 provider_series_id，但 `CompletenessIssue` 不携带 source frequency；severity 因而只能依赖具体 symbol/date/count 硬编码。
4. 检查 warning 的 `QualityResult` 写入路径：`period_start` 会单独持久化，message 会持久化 issue 描述。为保证审计信息完整，在 `history_gap` issue 中补充 source frequency，并让 message 明确包含 provider_series_id；缺口数量仍同时保留在结构化 issue 字段和 message 中。
5. 独立判断本次不应放宽 `require_contiguous` 或伪造缺失点。正确边界是只改变特定上下文下 issue 的 severity，完整性检测本身继续报告真实缺口。

## 3. 解决流程

采用 TDD 红—绿循环：

1. 先更新 `ingestion_issue_severity` seam 的参数化测试，用生产分布对应的 weekly/monthly/quarterly/annual 缺口数量验证 warning，并验证 daily、incremental、vintage_backfill、其他 Provider、未知频率仍 blocking。
2. 在 ingestion completeness 测试中验证 `history_gap` issue 携带 `source_frequency`、`missing_period_count`、首个缺口 `period_start` 和 `provider_series_id`。
3. 红灯结果：10 failed、36 passed；失败均准确指向 `CompletenessIssue` 缺少 `source_frequency`。
4. 最小实现：给 `CompletenessIssue` 增加可选 `source_frequency`；创建 `history_gap` 时写入规范化后的 frequency；删除 USUR 日期/数量硬编码，改为只在 `TRADINGVIEW_WEB + mode=backfill + code=history_gap + frequency in {weekly, monthly, quarterly, annual}` 时返回 warning。
5. 目标测试转绿后运行静态检查和全量后端回归。

没有修改 API、Web、schema、migration、registry，也没有写入缺失 observation 或改变任何其他完整性规则。

## 4. Agents、skills、tools 与文档

- Agents：仅当前研发执行线程；未创建或调用其他 Agent。
- Skill：`tdd`，用于约束已确认 seam 上的红—绿垂直切片、避免实现细节测试和内部 mock。
- Tools：`exec_command` 用于 Git/代码检索/测试/静态检查，`apply_patch` 用于所有文件修改。
- 已读项目文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`CONTEXT.md`。
- 已读开发链路宪法：`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`。
- 已读 skill 文档：`tdd/SKILL.md`、`tdd/tests.md`、`tdd/mocking.md`。
- 执行阶段：01 本地开发与候选冻结；未进入 PR、合并、标签、服务器部署或真实生产验收阶段。

## 5. 验证证据

- 目标测试：`py -3.12 -m pytest backend/tests/test_sync_provider.py backend/tests/test_ingestion_completeness.py -q` → `46 passed`。
- Ruff：`py -3.12 -m ruff check backend` → passed。
- Mypy：`py -3.12 -m mypy backend/src` → `Success: no issues found in 74 source files`。
- 全后端测试：`py -3.12 -m pytest backend/tests -q` → `346 passed, 5 warnings`；warnings 为既有 FastAPI/Starlette 弃用提示。
- `git diff --check` → passed。
- Web lint/test/build：未完成。独立 worktree 没有 `node_modules`，首次 lint 在加载 eslint 前失败；主工作区现有依赖对应的 lockfile SHA-256 与本任务基线 lockfile 不一致，因此没有复用或下载安装。此次无 Web 改动。
- 本地未启动或修改 Docker 容器，未启动应用进程，也未连接远程服务端点。

## 6. 值得沉淀的经验与模式

1. 数据质量检查和处置策略应分离：检查层忠实产生 `history_gap` 及审计元数据，处置层根据 provider、运行模式、issue code 和数据频率决定 blocking/warning。不要为单一 symbol/date 在通用同步任务中永久硬编码。
2. 降级策略必须写成正向白名单，并为每一个保持 blocking 的维度提供反例测试。这样可以防止“修复 quarantine”演变成全局关闭完整性门禁。
3. warning 不是丢弃问题。即使允许发布，也必须保留 provider_series_id、缺口数量和首个缺口，才能支持后续生产审计。
4. 生产统计在没有直接数据连接时应标注为“用户提供证据”，本地代码结论和测试结果则单独作为已核实事实。
5. 新 worktree 的依赖门禁不能借用 lockfile 不匹配的缓存，否则通过结果不具备候选版本证明力。

## 7. 更好的初始提示词

> 修复 MacroLens 的 TradingView 历史回填质量策略。生产回填已经抓到实际点，但 weekly/monthly/quarterly/annual 序列可能存在真实非连续历史，当前 `history_gap` 会 quarantine 整条序列。请从 origin/master 的指定提交创建独立 worktree，先写测试，再把 severity 调整为：仅 `TRADINGVIEW_WEB`、精确 `mode=backfill`、精确 `code=history_gap`、频率为 weekly/monthly/quarterly/annual 时 warning；daily、incremental/vintage_backfill、其他 Provider、其他 issue 一律保持 blocking。不要补造缺失值，不要关闭 contiguous 检查。warning 必须能审计 source frequency、provider_series_id、缺口数量和首个缺口。删除原来针对单一 TradingView symbol/date/count 的例外。只改 ingestion quality、sync、相关测试和结论报告，运行目标测试、ruff、mypy、全后端测试，提交但不 push/merge/deploy。

## 8. 当前场景的更优一次解决方案提示词

当前实现已经采用风险最小的策略边界：完整性规则不变，只在同步处置层按四维白名单降级。若要提高一次完成率，可把测试真值表和持久化证据写得更明确：

> 在独立 worktree 中用 TDD 修改 TradingView `history_gap` severity。先在 `test_sync_provider.py` 建立真值表：TV/backfill/history_gap 的 weekly、monthly、quarterly、annual（分别可使用 21、46、3、4 个缺口）必须 warning；daily、frequency=None、incremental、vintage_backfill、FRED 和 conflicting_duplicate 必须 blocking。再在 completeness 测试中构造一个月度中间缺口，断言 issue 的 `source_frequency=monthly`、provider_series_id、missing_period_count=1、period_start=首个缺口。实现时让 `CompletenessIssue` 新增末尾可选字段以保持调用兼容，在 `history_gap` 创建点填入已 lower-case 的 frequency，并让持久化 message 包含 provider_series_id 和缺口数；用 `period_start` 保存首缺口。删除 USUR 2025-10 单点例外，使用集中白名单常量。不要修改 contiguous 算法、observation、数据库/API/Web/registry。最后运行目标测试、ruff、mypy、全 backend pytest、diff 检查并提交，报告未执行门禁的具体原因，不 push/merge/deploy。
