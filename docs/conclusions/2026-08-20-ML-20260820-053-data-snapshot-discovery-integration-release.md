# ML-20260820-053｜DataBrowser latest snapshot discovery 集成发布报告

## 1. 问题与场景

- 任务：审查并发布 DataBrowser 在同步成功后的 latest snapshot discovery，不部署。
- 基线：`origin/master` / `fd500fc379d7088471f1849faf3adb58c14a8264`。
- 输入候选：`3f3272f188433c8ea4071a226705bad460a831b3`。
- 发布分支：`codex/ML-20260820-053-data-snapshot-discovery`。
- PR：[liuwlx/macrolens#32](https://github.com/liuwlx/macrolens/pull/32)。
- 场景要求：provider latest、single history、bulk history 三条成功路径在 invalidations 之后用不含 `data_as_of` 的请求发现最新快照；只显示现有 banner，不自动切换研究上下文；失败或 partial result 不提示；并发去重且卸载安全；无 backend/API/schema 改动。

## 2. 分析过程与发现

1. 确认远端 `origin/master` 精确指向任务基线，候选以该基线为唯一父提交，差异只有两个 Web 文件和任务 052 报告。
2. Standards/Spec 双轴审查确认候选总体边界正确，但发现两个发布阻断：
   - single-history 只判断 Job 顶层 `succeeded`，没有识别 `failed_count > 0`、`partial_success`、`partial_failure` 等结果级部分失败，可能错误显示新快照 banner。
   - discovery 只复用当前 in-flight Promise；若同步前的检查仍在运行，同步完成后的调用会复用旧请求，无法保证 invalidations 之后再执行一次 latest-check。
3. 核对后端实际 Job result 契约：TradingView 同步结果会返回 `failed_count` 与 `status: partial_success`；bulk 聚合会映射为 `partial_failure`。因此第一项不是理论风险，而是与现有契约直接相关。
4. 修复后再次进行 Spec/Standards 复核：Spec 无剩余发布阻断；命名问题已通过 `discoverLatestSnapshot` / `latestSnapshotRequest` 消除。测试 mock 的少量重复被判定为非阻断判断项，未为消除测试重复引入额外抽象。

事实与判断分离：三条成功路径、失败抑制、无自动上下文切换和无后端差异均有代码与测试证据；“低风险”是基于变更仅限 Web 发现流程且不改变 API/schema 的工程判断。

## 3. 解决流程

1. 在独立 worktree `E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260820-053-integration-release` 从候选创建发布分支，未修改主工作区，也未回滚其他 worktree。
2. 增加统一的 result failure 判定，provider latest 与 single history 仅在完整成功时发现最新快照；bulk 仅在 `status === succeeded` 时发现。
3. 将 discovery 改为单 in-flight drain：并发调用合并；运行期间的新请求只排队一次 trailing check；因此同步完成后的 invalidations 不会被同步前旧请求吞掉。
4. 页面卸载时清除 queued 标记，并在请求结果更新 UI 前检查 mounted 状态。
5. 补充 provider/single/bulk 成功与 partial/failed 负向测试、并发 trailing 去重测试、卸载丢弃 trailing 测试；最终 DataBrowser 定向测试为 16/16。
6. 使用 Python 3.12.9、Node 22.14.0 执行完整本地门禁。首次后端测试命令因未设置 `PYTHONPATH` 只产生模块收集错误、没有执行测试；按 CI 明确设置 `PYTHONPATH=backend/src` 后 346/346 通过。首次定向 Web 测试的子进程误取 Node 20，修正命令 PATH 后通过；两者均为命令环境问题，不是产品失败。
7. 提交修复 `afe6e62`，推送发布分支并创建 PR #32；报告作为独立文档提交到同一 PR。PR 四项 CI 全绿后合并，并在合并提交上创建 `v2026.08.20-data-snapshot-discovery`。不执行部署。

## 4. Agents、skills、tools 与文档

### Agents

- 主执行 Agent：集成发布、契约核对、修复、测试、Git/PR/标签收口。
- Standards 审查子 Agent：检查项目规范与 smell baseline，指出命名和流程证据问题。
- Spec 审查子 Agent：发现 result-level partial failure 与 trailing check 两个阻断，并在修复后复核通过。

### Skills

- `code-review`：固定基线，隔离 Standards/Spec 双轴审查并在修复后复核。
- `github`：按明确授权执行分支推送、单一 PR、CI 检查、合并与标签发布。

### Tools

- Git / Git worktree：基线、候选、差异、独立工作树、提交、推送和标签。
- GitHub CLI：PR 创建、检查状态、合并和远端结果核实。
- `apply_patch`：只修改目标 Web 文件并新增本报告。
- `rg` / PowerShell：定位 Job result 契约、测试脚本、OpenAPI current 命令和检查证据。
- Python 3.12 工具链：ruff、mypy、pytest、OpenAPI check。
- Node 22 / npm：Web lint、Vitest、Next.js production build。

### 已读取文档

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `CONTEXT.md`
- `docs/governance/development-constitutions/README.md`
- `docs/governance/development-constitutions/01-local-development-and-freeze.md`
- `docs/governance/development-constitutions/02-pr-merge-and-release.md`
- `code-review/SKILL.md`
- `github/SKILL.md`
- `apps/web/lib/types.ts`
- `backend/src/macrolens_worker/tasks/sync.py`
- `backend/src/macrolens_api/routers/admin.py`
- `.github/workflows/ci.yml`
- `scripts/generate_openapi.py`

## 5. 验证证据与可沉淀经验

### 本地门禁

- `ruff check backend`：通过。
- `mypy backend/src`：通过，74 个 source files。
- `PYTHONPATH=backend/src pytest backend/tests`：346 passed，5 个既有 deprecation warnings。
- `npm --workspace apps/web run lint`：0 errors，2 个既有 warnings。
- `npm --workspace apps/web run test`：14 files / 59 tests passed。
- `npm --workspace apps/web run build`：通过，包含 TypeScript 与 14 个静态页面生成。
- `PYTHONPATH=backend/src python scripts/generate_openapi.py --check`：`OpenAPI is current: 75 paths`。
- `git diff --check`：通过。
- 最终差异边界：Web 组件、Web 测试及结论报告；无 backend、API、OpenAPI、database schema、migration 或 seed 变更。

### 经验与模式

- Job 顶层 `succeeded` 只表示任务执行完成，不等于业务结果完整成功；UI 成功提示必须同时识别 result-level 计数和状态。
- 并发去重不能只做“复用当前 Promise”。当调用语义要求“某事件之后重新检查”时，需要 coalesced trailing edge：当前请求期间的新触发合并为恰好一次后续检查。
- 卸载安全应同时控制 UI state write、轮询/请求取消和 queued follow-up；只防 React state update 不足以证明不会继续产生无用流量。
- 本地门禁必须记录实际运行时和环境变量。命令名称相同但子进程运行时不同，会产生与代码无关的假失败。
- 历史任务报告不应被新集成任务改写；新增集成发布报告记录候选后的审查修复和门禁证据，保留任务演进链。

## 6. 更好的初始提示词

> 请在独立 worktree 中审查并发布候选提交 `3f3272f`（基线 `fd500fc`）的 DataBrowser 同步后新快照提示。请不要只检查 Job 顶层状态：核对后端实际 result 契约，确保 provider latest、单序列 history、批量 history 只有完整成功才在所有 query invalidations 完成后，用不含 `data_as_of` 的请求检查最新快照；任何 failed、failed_count、partial_success、partial_failure 都不得提示。并发时允许合并请求，但同步完成后的触发不能复用同步前的旧结果，至少要保留一次 trailing check；页面卸载后不得更新状态或继续排队检查。保持研究上下文不自动切换，不改 backend/API/schema。补齐针对三条路径、partial/failed、并发 trailing 和卸载的测试，跑 ruff、mypy、全部 backend tests、Web lint/test/build 和 OpenAPI current。全绿后提交、推送指定分支、创建非 draft PR，等待四项 CI 全绿后合并 master，并在合并提交创建指定标签；不部署。最后输出 PR、合并 SHA、标签和结论报告。

## 7. 更优的一次解决方案提示词

> 作为 MacroLens 集成发布负责人，先读取项目/组织规则、CONTEXT 和 01/02 宪法，在独立 worktree 将候选 `3f3272f` 与基线 `fd500fc` 做 Standards/Spec 双轴审查。把“完整成功”定义为：Job 顶层 succeeded 且 result.failed_count 为 0，result.status 不属于 partial_success、partial_failure、failed；bulk 仅 status=succeeded。实现一个 trailing-edge coalescing 的 latest discovery drain：任意时刻最多一个请求，运行期间的新触发合并成一次后续请求，后续请求必须发生在各成功路径 invalidations 完成之后；所有 latest 请求省略 data_as_of，结果只显示现有 banner，用户点击后才更新 URL。卸载时清空 pending、停止轮询/取消可取消请求并禁止 state write。为 provider/single/bulk 完整成功、各类 partial/failed、同步前已有 in-flight、多个并发成功仅一次 trailing、卸载丢弃 trailing 建立回归测试。确认 git diff 不含 backend/API/OpenAPI/schema/migration/seed，使用 Python 3.12+、Node 22 和 CI 同样的 PYTHONPATH 跑完整门禁。若发现问题先修复再复核；全绿后按 `codex/ML-20260820-053-data-snapshot-discovery` → PR → 四项 CI → merge master → `v2026.08.20-data-snapshot-discovery` 收口，全程不部署，并生成 `docs/conclusions` 报告。

