# ML-20260820-043 TradingView backfill `symbol_errors` 修复报告

- 状态：`REVIEW`
- 任务 ID：`ML-20260820-043`
- 基线：`6112fe5df6b11d4471393bc4514b577c4e81b97f`
- 分支：`codex/ML-20260820-043-tradingview-symbol-errors`
- 独立 worktree：`E:/workerspace/projects/20260709/macrolens-worktrees/ML-20260820-043-engineering-03`
- 开发阶段：01 本地开发与候选冻结
- API、Schema、存储影响：无

## 1. 本次遇到的问题以及场景

TradingView 历史回填已经成功取得并规范化图表历史数据，但 `sync_provider` 随后读取
`TradingViewAdapter.symbol_errors` 时抛出 `AttributeError`，使整个 Job 在发布数据库结果前失败。
用户提供的生产证据是 Job `ec35a730-2c56-4bd4-ab65-e134172854d6` 连续失败三次且数据库未发布；
本任务没有连接生产数据库，因此该 Job 状态属于用户提供、未在本地独立复核的事实输入。

代码中 `symbol_errors` 只有类型注解，没有实例运行时默认值。`latest`/`incremental` 路径原先会在
抓取前赋值 `{}`，而 `backfill` 在该赋值之前直接进入 `_fetch_history` 并返回。调用方又针对任何
`TradingViewAdapter` 无条件读取该属性，因此成功抓取后仍会在后处理阶段失败。

## 2. 分析这个问题的过程

先固定用户指定的 `origin/master` 合并 SHA，并在独立 worktree 中检查公开 seam、调用方和现有测试。
公开 seam 已由任务卡明确指定为 `TradingViewAdapter.fetch(mode="backfill")`，现有
`test_fetch_backfill_persists_chart_history_without_raw_payload` 已完整驱动 WebSocket 历史抓取路径，
无需新增内部 Mock 或绕过接口。

按 `diagnosing-bugs` 排列并验证假设：首要假设是 backfill 提前返回导致实例属性从未创建；次要假设
包括实例复用后的陈旧状态、基类构造函数已创建属性、以及问题只存在于调用方。检查基类确认构造函数
只设置 `client`。在既有 backfill 测试追加 `adapter.symbol_errors == {}` 后，定向命令稳定 RED，准确
抛出与生产相同的 `AttributeError`，从而排除“基类已初始化”和“仅调用方有问题”。

## 3. 解决这个问题的工作流程

1. 读取项目、组织和阶段 01 规则，确认任务卡、基线、范围和禁止事项。
2. 从 `6112fe5...` 创建独立分支和 worktree，不接触主工作区已有改动。
3. 在公开 backfill seam 的既有测试中先追加空错误字典断言。
4. 运行目标测试得到 RED：`AttributeError: 'TradingViewAdapter' object has no attribute 'symbol_errors'`。
5. 最小修改生产代码：把 `self.symbol_errors = {}` 从 latest 专属分支移到 `fetch` 入口。
6. 重跑同一目标测试得到 GREEN，再跑完整 TradingView provider 测试和修改文件 Ruff。
7. 补跑根规则列出的完整后端与 Web 门禁，确认候选没有跨模块回归。
8. 检查 diff、受跟踪副作用和工作区范围，生成本报告并冻结候选提交。

## 4. 使用的 Agents、skills、tools 以及阅读文档

- Agents：Codex 当前执行 Agent；未创建 subagent、部门线程或其他用户可见任务。
- Skills：`diagnosing-bugs` 用于建立精确 RED 反馈环、列出可证伪假设和清理验证；`tdd` 用于在公开
  seam 上执行测试先行的 RED→GREEN。
- Tools：`exec_command`、`write_stdin`、`apply_patch`、Git/worktree、`rg`、PowerShell、Python
  3.12、pytest、Ruff、mypy、Node 22、npm、ESLint、Vitest、Next build。
- 已读项目文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、
  `docs/governance/development-constitutions/README.md`、
  `docs/governance/development-constitutions/01-local-development-and-freeze.md`、`CONTEXT.md`。
- 已读 skill 文档：`diagnosing-bugs/SKILL.md`、`tdd/SKILL.md`、`tdd/tests.md`、
  `tdd/mocking.md`。
- 相关 ADR：仓库未发现 TradingView 对应 ADR；本基线也不存在检索到的两份 TradingView 架构候选
  文档，因此本次以代码、调用方、公开测试和任务证据为依据。

阶段 01 完成证据：

- RED：Python 3.11 临时环境运行目标测试，`1 failed`，失败点为新增断言，精确报
  `AttributeError`。随后所有正式验收均改用项目要求的 Python 3.12。
- 目标测试（Python 3.12）：`1 passed in 0.44s`。
- `backend/tests/test_tradingview_provider.py`：`15 passed in 0.39s`。
- 修改文件 Ruff：`All checks passed!`。
- `ruff check backend`：通过。
- `mypy backend/src`：`Success: no issues found in 74 source files`。
- `pytest backend/tests`：`327 passed, 5 warnings in 17.75s`；warning 为既有 FastAPI/Starlette
  deprecated API 提示。
- `npm --workspace apps/web run lint`（Node 22.14.0）：退出 0，有 2 个既有 warning、0 error。
- `npm --workspace apps/web run test`（Node 22.14.0）：13 个文件、43 项测试通过。
- `npm --workspace apps/web run build`（Node 22.14.0）：编译、类型检查和 14 个页面生成通过。
- 首次 Web test 曾因 npm lifecycle 从 PATH 选中 Node 20.11.1 而在收集阶段触发依赖 ESM 错误；
  将 Node 22.14.0 置于该命令进程 PATH 首位后，lint/test/build 全部通过。该失败不是产品测试失败。
- `git diff --check`：通过；安装依赖和构建未修改受跟踪 Web 文件。
- 未启动或修改 Docker、未连接远程服务、未推送、未合并、未部署。

## 5. 本次执行值得沉淀的经验或者模式

1. 类级类型注解只描述类型，不会创建实例属性；被跨模式调用方读取的诊断状态必须在所有返回路径
   之前建立运行时不变量。
2. 模式分支中的提前返回是状态初始化遗漏的高风险点。每次调用都要重置的状态应位于公共入口，避免
   backfill/空映射缺失属性，也避免实例复用时泄漏上一次 latest 的错误。
3. 现有成功路径测试已经是正确 seam 时，应在原测试增加最小行为断言，而不是为同一路径复制大量
   WebSocket fixture。
4. 先断言准确的缺失状态再修复，比只测试“调用不抛错”更能锁定此类后处理崩溃。
5. Windows 上显式调用新版 npm 不保证 lifecycle 使用同版本 Node；验收脚本应同时固定 PATH 并输出
   `node --version`。

## 6. 问题解决后反推的一条更好的初始提示词

> TradingView 历史回填已成功抓到数据，但任务在发布前读取 adapter 的逐 symbol 错误信息时提示该
> 属性不存在。请在独立 worktree 中，用现有公开 backfill fetch 测试先断言成功回填后的错误信息为
> 空字典并确认测试会失败；然后让每种 fetch 模式从调用开始就初始化这份错误信息，保持 latest 的
> 原有错误收集行为，不改 API、数据库 schema 或存储。运行目标测试、整个 TradingView provider
> 测试、修改文件静态检查和项目规定门禁，生成结论报告并提交，但不要 push、merge 或 deploy。

## 7. 当前场景是否有更优方案及一次解决的更优提示词

当前一行位置移动是本任务约束下的最优方案：它同时覆盖 backfill、空 mappings、latest 和
incremental 的入口初始化，并保证每次 fetch 清除旧状态。若允许扩大防御性测试，进一步的方案是让
`symbol_errors` 在 adapter 构造完成后就始终存在，同时仍在每次 fetch 开始时清空，并新增“空映射”
与“同一 adapter 连续 latest→backfill”两项契约测试；这样即使未来调用方在 fetch 前读取属性也不会
出错，并能锁定实例复用不泄漏状态的约束。当前任务没有这种调用需求，因此没有扩大生产改动。

> 请把 TradingView adapter 的 `symbol_errors` 定义为完整生命周期不变量：构造后一定存在，每次
> fetch 开始清空，latest/incremental 可填充错误，backfill 和空映射成功后保持空字典。先用公开接口
> 为 backfill、空映射、同实例 latest→backfill 三个场景分别建立 RED；再做最小实现并验证调用方可
> 无条件读取。禁止改 API/schema/存储，完成全量门禁、报告和本地 commit，不 push/merge/deploy。
