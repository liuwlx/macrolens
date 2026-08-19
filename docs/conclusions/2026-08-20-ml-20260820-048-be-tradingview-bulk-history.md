# ML-20260820-048-BE｜TradingView 批量历史回填后端实现

## 1. 问题与场景

管理员需要从 `origin/master@6e757bc0e644bbb7b6f99ecb8b942d7e0921df5e` 手动批量回填剩余的
verified-primary `TRADINGVIEW_WEB` Series。现有接口一次只能提交一个 Series，按最近 50 个 Job
查重，不能表示最多 500 个 child 的批次进度；并发 child 还可能同时改写 Provider 级
`PublicationBatch` active 链。本任务要求不新增表、不改 Web、不执行 push/merge/deploy。

实施在独立 worktree
`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260820-048-BE` 和分支
`codex/ML-20260820-048-BE` 中完成，未触碰主工作区的他人改动。

## 2. 分析过程

1. 核对基线、现有单 Series Admin API、Job JSONB/幂等键、Worker claim/dispatch、
   `sync_provider` 与 PublicationBatch 发布路径。
2. 核实 195 个 `UNAVAILABLE_US` 已是 disabled + non-primary，因此 verified-primary 查询会自然排除，
   不应硬编码 195 或 339。
3. 将 durable Job 作为无新表条件下的批次事实来源：每个 child 保存 `history_batch_id`、请求摘要和
   批次统计元数据；GET 直接按 JSONB `history_batch_id` 查询全部 Job，不使用 `/admin/jobs` 的 limit。
4. 明确计数语义：`total` 是全部 eligible，`candidate_count` 是排除已有 succeeded scoped backfill
   后的剩余数，`limit` 只截取本批实际 child；`skipped_completed` 是 eligible 与已完成 Source ID 的交集。
5. 为“全部已完成”且没有 child 的情况保留一个终态 `history_batch_marker` Job，使 `empty` 批次仍可重放、
   可由 GET 查询；marker 不进入 Worker，也不计入 child 状态。
6. API 创建事务取得独立命名空间的 Provider advisory xact lock，先重放同请求 key，再复用仍有
   queued/running child 的 active batch，最后一次 bulk `INSERT ... ON CONFLICT DO NOTHING` 原子 reserve。
7. Worker 仅对 `TRADINGVIEW_WEB + backfill` 取得另一命名空间的 Provider advisory xact lock，事务提交前
   不释放，从而让实际 PublicationBatch 发布链串行，同时不阻塞 latest 或其他 Provider。

## 3. 解决流程与实现结果

- 新增 `HistoryBatchCreate`、`HistoryBatchFailure`、`HistoryBatchPublic`，状态覆盖
  queued/running/succeeded/partial_failure/failed/empty。
- 新增：
  - `POST /api/v1/admin/providers/{provider_code}/history`（202）；
  - `GET /api/v1/admin/providers/{provider_code}/history/{batch_id}`。
- 两个端点继续通过 `AdminUser` dependency 限制管理员；非 TradingView 使用现有 `AppError` problem
  details；inactive Provider 返回 404 problem details。
- child 保持 `job_type=sync_provider`、单 `source_series_ids=[id]`、priority 5、max_attempts 1；幂等键为
  `manual-history-batch:{sha256(request_key)}:{source_id}`。
- 候选按 annual → quarterly → monthly → weekly → daily，再 SourceSeries ID 排序，最多选择请求 limit。
- GET 汇总 Job 状态和 result 的 inserted/revised/unchanged/staged；终态 Job failure 与 succeeded Job 的
  `partial_success/failed_count` 均进入失败计数和明细。
- 未新增 schema、migration 或业务表；未修改 TradingView decoder、vintage 规则和 Web。

## 4. Agents、skills、tools 与文档

- Agents：当前后端研发 Codex Agent；未创建子 Agent，也未接管其他线程。
- Skill：`tdd`。完整阅读 `SKILL.md`、`tests.md`、`mocking.md`，按 API、durable Job、Worker sync、
  schema/OpenAPI 公共 seam 执行 RED→GREEN。
- Tools：PowerShell、Git 只读/提交命令、`rg`、`apply_patch`、pytest、ruff、mypy、OpenAPI 生成脚本、
  npm/Vitest/Next build、计划工具。
- 已读规则和上下文：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、
  `CONTEXT.md`、`docs/governance/development-constitutions/README.md`、
  `01-local-development-and-freeze.md`、047-A 架构调查、047-B 回填审计，以及相关源码、测试和契约。
- 开发阶段：01 本地开发与候选冻结。完成证据是独立 worktree、预期文件范围、完整检查结果和候选提交；
  未进入 02 PR/发布或 03 服务器部署阶段。

## 5. RED/GREEN、检查证据与经验

RED 证据：

- API 首个切片：`HistoryBatchCreate` 不存在，目标测试在正确 Python 3.12 环境中 collection failed。
- Worker 锁切片：`test_tradingview_backfill_acquires_provider_transaction_lock` 断言失败，证明旧实现没有
  `pg_advisory_xact_lock`。
- 契约切片：`scripts/generate_openapi.py --check` 返回 `macrolens_openapi.yaml is out of date`。

GREEN 证据：

- 目标测试：37 passed（history API、sync provider、registry/schema）。
- `ruff check backend`：通过。
- `mypy backend/src`：74 source files，无问题。
- `pytest backend/tests`：342 passed，5 个既有 deprecation warning。
- OpenAPI check：current，75 paths；YAML/JSON 均重新生成。基线 JSON 原先落后当前 app，因此 JSON diff
  同时恢复了它与生成结果的一致性。
- Web lint：0 error、2 个基线 warning；Web tests：43/43；Web production build：通过。
  初次用 PATH 中的 Node 20.11.1 时 Vitest 因 ESM 依赖在 collection 阶段失败；切换本机已有且满足工程要求的
  Node 22.14.0 后通过，未修改 Web 源码。
- 未启动本地 Docker/Compose，未访问远程 Provider 或数据库，未 push/merge/deploy。

值得沉淀的模式：

1. 无专用批次表时，可把 correlation ID 和不可变批次元数据复制进 child durable Job；但空批次必须有
   durable marker，否则 POST 返回的 UUID 无法被 GET 重放。
2. API fan-out 的原子性与 Worker 发布的串行性是两层不同约束，应使用不同 advisory lock namespace，
   避免 POST 被长时间 Provider 抓取事务阻塞。
3. 批次失败不能只看 Job.status；Worker 的 partial-success result 也可能代表单 Series 没有可用观测。
4. bulk insert + unique idempotency key 解决请求重放，provider-scoped creation lock 解决不同请求 key 的并发 fan-out；
   两者不能互相替代。

## 6. 反推的更好初始提示词

> 请从指定 origin/master SHA 创建独立 worktree，以 TDD 实现管理员 TradingView 批量历史回填后端。
> 先读取项目/组织/CONTEXT/开发宪法与 TDD 规则。新增带 body idempotency_key(8..200)、limit(1..500，
> 默认 500) 的 batch POST 和按 batch UUID 查询的 GET；明确 total=全部 eligible、candidate_count=排除已成功
> scoped backfill 后的剩余数、limit=本批 child 上限。候选只取 active Provider/Dataset 下 verified-primary，
> 按 annual→quarterly→monthly→weekly→daily、Source ID 排序。每个 child 仍是单 Source sync_provider，
> priority=5、max_attempts=1，payload 保存 batch ID/元数据，请求摘要+Source ID 构成幂等键。不能新增表；
> 请设计 durable empty batch。POST 用独立 Provider advisory xact lock 原子 bulk reserve、重放相同 key、复用
> queued/running active batch；GET 不使用通用 Job limit，汇总 status/result/失败明细。Worker 对 TV backfill 用另一
> Provider advisory xact lock 串行 PublicationBatch。先保留 RED，再实现 GREEN，更新 YAML/JSON OpenAPI，跑目标
> tests、ruff、mypy、全 backend pytest 和项目规定 Web 门禁，生成结论报告并提交，不 push/merge/deploy。

## 7. 当前场景一次解决的更优方案提示词

> 在现有 Job 表上实现一个小型、可复用的 batch orchestration service，而不是把所有编排细节堆在 Admin router：
> service 负责 request replay、active batch reuse、eligible/skip/select、bulk reserve、empty marker 和 Job result
> aggregation，router 只处理 Provider 校验与 response。保持本任务的公共 API、单 Series child、两套 provider
> advisory lock namespace、无 migration 约束不变。增加真实 PostgreSQL 集成测试，使用两个并发事务验证：不同
> request key 只产生一个 active batch、bulk reserve 全有或全无、GET 可见完整 500 children、两个 backfill 的
> PublicationBatch active 链始终只有一个；单元测试继续覆盖排序、计数、partial-success failure 与 empty replay。
> 完成后生成 OpenAPI、跑完整门禁、报告数据库集成测试端点与证据，只提交不发布。
