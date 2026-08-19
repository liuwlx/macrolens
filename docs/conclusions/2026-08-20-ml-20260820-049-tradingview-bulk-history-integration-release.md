# ML-20260820-049｜TradingView 批量历史功能集成发布

## 1. 问题与场景

本任务由集成发布部负责，将同一精确基线
`origin/master@6e757bc0e644bbb7b6f99ecb8b942d7e0921df5e` 上的后端/OpenAPI 候选
`88c21dfb9464d62bdec0e8874414c98b2a917224` 与 Web 候选
`3e51b87f38a513a09c26d8b40c529ca5f50a73b9` 集成为一个可发布候选。

工作在独立 worktree
`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260820-049-integration-release`
和分支 `codex/ML-20260820-049-tradingview-bulk-history` 中完成。主工作区存在大量其他工作者的未提交
改动，本任务未触碰、覆盖或回滚这些改动。任务只覆盖本地冻结和 PR/版本发布，不部署。

## 2. 分析与独立审查

两候选均以指定基线为唯一父提交，无 cherry-pick 冲突；集成后提交分别为：

- Backend/OpenAPI：原候选 `88c21dfb9464d62bdec0e8874414c98b2a917224`，集成提交 `664e06f`。
- Web：原候选 `3e51b87f38a513a09c26d8b40c529ca5f50a73b9`，集成提交 `7acba40`。

按 `code-review` 技能执行 Standards 与 Spec 两个隔离审查 Agent。首次审查发现：

1. active batch 复用没有持久化新请求幂等键与被复用批次的关联；批次结束后重试可能另建批次。
2. Web 的 `failures: unknown[]` 与后端 `HistoryBatchFailure` 不完全一致。
3. 批量按钮在非 TradingView 上下文仍显示为禁用，违反本任务“只在 admin + live + TradingView
   上下文显示”的明确要求。
4. 页面卸载只取消轮询定时器，没有中止已发出的 batch POST/GET。
5. 完整后端门禁进一步发现 Web 使用硬编码 Provider URL，无法通过仓库的前端调用到 OpenAPI
   参数化路径一致性检查。

修复提交 `b816932` 最小化解决上述问题：active reuse 写入 durable replay marker；Web 恢复结构化失败
类型；按钮按完整上下文条件渲染；轮询使用 `AbortController`；URL 使用参数化模板。补充了 active reuse
后重试、339 个剩余 child 一次入队、非 TradingView 隐藏及 in-flight GET 卸载中止测试。

复审结果：Spec 轴无剩余可执行发现。Standards 轴只保留将 JSON Job payload 抽成 typed batch service、
合并单/批 reserve 重复逻辑、集中 Web 状态映射等可选重构建议；本次为避免扩大集成范围未实施。

## 3. 解决流程与关键验收

1. 从远程重新 fetch，并确认 `origin/master` 仍精确等于指定基线；目标远程分支和版本标签均不存在。
2. 创建独立 integration worktree/branch，按 Backend/OpenAPI → Web 顺序 cherry-pick。
3. 对公共契约、eligible/skip、幂等与 active reuse、339 child、Job 重试/优先级、Worker 事务锁、
   UI 条件与轮询生命周期、禁止项、OpenAPI 生成物逐项审查。
4. 修复审查和门禁发现，运行定向测试、独立复审和完整门禁。
5. 冻结候选后进入阶段 02：push、PR、等待 backend/frontend/containers/acceptance 全绿、合并 master、
   在合并 SHA 创建唯一标签。PR、合并 SHA 和标签由任务最终回执记录，因为这些标识在报告提交进入 PR
   前尚不存在。

关键事实：

- eligible SQL 仅取 active Provider/Dataset 下 `mapping_status=verified` 且 `is_primary=true`；
  seed 中 `UNAVAILABLE_US` 会成为 disabled + non-primary，因此被排除。
- succeeded、单 Source 的 backfill Job 会进入 completed 集合并从候选中跳过。
- 默认 `limit=500` 的测试直接验证 340 eligible、1 completed 时一次 reserve 剩余 339 个 child。
- 每个 child 为独立 `sync_provider` Job，`priority=5`、`max_attempts=1`；一个 child 失败不会改变
  其他 child 的 Job 事务。
- API 创建锁与 Worker Provider backfill 锁使用不同 advisory xact lock namespace；Worker 锁在 fetch
  和 PublicationBatch 处理前取得，并由事务保持到 commit。
- 空候选使用 durable `history_batch_marker`，POST 返回的 empty batch 可由 GET 查询和幂等重放。
- 未新增 migration、table 或 scheduler；保留原单 Series 历史同步按钮；未启动 Docker/Compose。

## 4. Agents、skills、tools 与已读文档

Agents：

- 当前集成发布 Agent：基线核验、集成、修复、门禁、冻结和阶段 02 发布。
- Standards 独立审查 Agent `Boole`。
- Spec 独立审查 Agent `Lorentz`。

Skills：

- `code-review`：强制把仓库规范与任务规格分成两个隔离审查轴；直接促成四项集成修复。
- `github:yeet`：约束发布前 scope/status 核验、显式提交、push 和 PR 描述。

Tools：

- Git、PowerShell、`rg`、`apply_patch`、Python 3.12.9、ruff、mypy、pytest。
- Node.js 22.14.0、npm、Vitest、ESLint、Next.js build。
- OpenAPI 生成脚本、并行审查 Agent、GitHub CLI/应用、计划工具。

已读文档：

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `CONTEXT.md`
- `docs/governance/development-constitutions/README.md`
- `docs/governance/development-constitutions/01-local-development-and-freeze.md`
- `docs/governance/development-constitutions/02-pr-merge-and-release.md`
- `code-review/SKILL.md`
- `github:yeet/SKILL.md`
- 两个候选实现报告、相关后端/Web 源码、测试和 OpenAPI 生成脚本。

## 5. 门禁证据、阶段与经验沉淀

最终本地冻结证据：

- `ruff check backend`：通过。
- `mypy backend/src`：74 个 source files，无问题。
- `pytest backend/tests`：343 passed，5 个既有 deprecation warning。
- `npm --workspace apps/web run lint`：0 error，2 个未修改文件中的既有 warning。
- `npm --workspace apps/web run test`：14 files、51 tests 全部通过。
- `npm --workspace apps/web run build`：Next.js 16.2.12 production build 通过，14 routes 完成。
- `python scripts/generate_openapi.py --check`：current，75 paths。
- `python scripts/generate_openapi.py --json` 后 Git 无变化，证明 YAML/JSON 都是生成器当前输出。

OpenAPI 大 diff 核验：基线 JSON 只有 62 paths，而同一基线 YAML 已有 73 paths；当前 YAML/JSON 均为
75 paths。本功能只在 YAML 语义上新增 2 个 batch paths 和 3 个 batch schemas；JSON 中其余 11 个
“新增”路径早已存在于基线 YAML，是把滞后的 JSON 恢复到同一生成器事实，不是本功能混入的无关 API 语义。

开发阶段：

- 01 本地开发与候选冻结：完成；独立 worktree、候选提交、完整门禁和无 Docker 证据齐全。
- 02 PR 合并与版本发布：按任务继续完成，结果由 PR、CI、merge SHA、唯一 tag 互相追溯。
- 03 服务器 Docker 部署与真实验收：明确不执行。

值得沉淀的模式：

1. “active batch 复用”和“request idempotency”是两个独立条件；复用时必须持久化新请求键的 replay alias。
2. UI 卸载取消既包含定时器，也包含已经发出的网络请求；mounted guard 不能代替 AbortSignal。
3. 跨栈集成必须运行最终组合的前端→OpenAPI 检查；两个候选各自通过不等于组合后通过。
4. 生成物大 diff 应同时用生成器零差异和语义集合对比解释，不能仅凭“生成文件”假定安全。
5. 结论报告必须同时记录原候选 SHA 与集成后的 SHA，避免 cherry-pick 后失去来源追溯。

## 6. 反推的更好初始提示词

> 请从 `origin/master@6e757bc0e644bbb7b6f99ecb8b942d7e0921df5e` 创建独立 integration
> worktree，集成 Backend/OpenAPI `88c21dfb9464d62bdec0e8874414c98b2a917224` 和 Web
> `3e51b87f38a513a09c26d8b40c529ca5f50a73b9`。逐项验证：后端/OpenAPI/Web 的
> HistoryBatchPublic（包括 failure item）完全同构；verified-primary 且排除 UNAVAILABLE_US；跳过
> succeeded scoped backfill；默认 limit=500 能一次 reserve 339 个 child；同请求重放和不同请求 active
> reuse 都必须 durable，复用后重试仍返回同一 batch；empty batch 可 GET；child priority=5、
> max_attempts=1、独立失败；Worker 在 fetch/publication 前取得 Provider advisory xact lock 并持有到
> commit；UI 仅 admin+live+TradingView 显示，轮询专用 GET，终态停止，unmount 同时取消 timer 和
> in-flight HTTP。不得增加 migration/table/scheduler，不删单 Series 按钮。用生成器验证 YAML/JSON
> OpenAPI current，并解释大 JSON diff 的语义集合。发现问题做最小修复并补测试，跑完整六项门禁，
> push 指定分支、建 PR、等四组 CI 全绿、合并 master、在 merge SHA 打唯一标签；不部署。

## 7. 当前场景一次解决的更优方案提示词

> 在上述集成约束不变的前提下，把无表 batch orchestration 收敛为一个 typed service：
> `HistoryBatchPayload` 统一创建 child、empty marker 和 active-reuse replay marker；service 负责
> eligible/skip/select、bulk reserve、幂等映射和聚合，router 只做认证与响应。增加真实 PostgreSQL 并发
> 测试，验证两个不同 request key 并发时只产生一个 active batch 且各自都可 durable replay，339 个
> child 全有或全无，两个 Worker backfill 的 PublicationBatch active 链不会交叉。Web 使用一个
> batch-status metadata map 和可取消 polling hook，统一活动/终态/错误样式与 AbortController 生命周期。
> 完成后执行同一份跨栈契约与完整发布门禁，再进入 PR/CI/merge/tag，不部署。
