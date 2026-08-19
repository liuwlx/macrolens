# ML-20260820-045｜TradingView USUR 已知历史缺口放行

## 1. 问题与场景

任务卡提供的生产证据是：TradingView `ECONOMICS:USUR` chart 有 942 个非空月度点，覆盖 1948-01 至 2026-07，唯一缺口为 2025-10；quality run `79c2ad10-fadf-48ec-bfb6-f1d73b5f3dba` 因 `history_gap` blocking 而未发布。本任务未重新访问生产 Provider 或数据库，因此上述数量和 run ID 属于用户提供、未在本地独立复核的事实输入。

目标是只把 `TRADINGVIEW_WEB + backfill + ECONOMICS:USUR + 2025-10-01` 这一真实已知单一缺口降为 warning，不补造 null 或数值；incremental、未知日期、未知 symbol、其他 Provider，以及同时出现额外缺口时继续 blocking。

## 2. 分析过程

现有 `CompletenessIssue` 只携带内部 `source_series_id` 和首个缺口日期，未携带 Provider symbol；`ingestion_issue_severity` 也没有 mode，无法做精确判定。调用点没有把 sync mode 传入严重级别函数，且缺失序列 warning 集合包含 `history_gap`，存在非精确放行风险。

进一步检查发现 completeness 会把多个历史缺口汇总为一个 issue，仅暴露第一个日期。若只匹配首日，USUR 在保留 2025-10 缺口的同时新增另一个缺口时可能被误放行。因此增加可选 `missing_period_count` 并要求其严格等于 1；这不是新增放行策略，而是保证默认 blocking 不能被汇总 issue 绕过。

## 3. 解决流程

1. 从精确基线 `f59bb60f6e60c5505df47cfd411a35d7fed422d2` 创建独立 worktree 和 `codex/ML-20260820-045-tradingview-known-gap` 分支，未触碰主工作区的他人改动。
2. 在约定公共 seam `ingestion_issue_severity` 先写 RED。首次有效 RED 为 3 failed，原因是 `CompletenessIssue` 不支持 `provider_series_id`；混合缺口旁路测试另取得 1 failed，原因是缺少机器可读缺口计数。
3. 为 `CompletenessIssue` 增加可选 `provider_series_id` 和 `missing_period_count`；创建 `history_gap` 时从 `SourceSeries` 填入 symbol，并记录实际缺口数。
4. 在 `sync.py` 定义唯一已知映射 `ECONOMICS:USUR -> 2025-10-01`。严重级别只在 TradingView、`mode == "backfill"`、`history_gap`、symbol/date 精确命中且缺口数为 1 时返回 warning；从一般缺失序列 warning 集合移除 `history_gap`。
5. sync 调用点显式传入 mode。测试以参数表覆盖唯一 warning 和所有默认 blocking 边界，没有增加数据库、registry、API、前端或部署策略。

本任务执行开发链路阶段 01（本地开发与候选冻结）。最终定向检查、完整后端门禁及 Web 门禁均通过；没有进入阶段 02/03，没有 push、merge、tag 或部署，也未启动 Docker、执行 seed/migration/sync 或写远程服务。

## 4. Agents、skills、tools 与文档

- Agents：仅当前 Codex 实现 Agent；未调用子 Agent。
- Skills：`diagnosing-bugs` 用于建立可重复 RED、区分环境失败和行为失败；`tdd` 用于按公共 seam 执行 RED→GREEN，并阅读其 `tests.md`、`mocking.md`。
- Tools：PowerShell 只读检查、`rg`、`apply_patch`、Git worktree/status/diff/commit、Python 3.12.9、pytest、Ruff、Mypy、Node 22.14.0、npm、ESLint、Vitest、Next build。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`CONTEXT.md`、`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`、`diagnosing-bugs/SKILL.md`、`tdd/SKILL.md` 及上述 TDD 参考文件。

验证证据：目标与相邻测试最终 42 passed；修改文件 Ruff 通过；完整 `ruff check backend` 通过；Mypy 为 74 个源文件无问题；完整后端 pytest 为 333 passed、5 条既有 FastAPI/Starlette 弃用 warning；Web lint 为 0 error、2 条既有 warning，Web test 为 43 passed，Web build 通过。首次系统 Python 3.11 测试因缺少项目包/boto3、首次 Web build 因临时跨根目录 junction 被 Turbopack 拒绝，均为工具入口问题，不计作代码 RED；改用项目 Python 3.12 venv 和 worktree 本地 npm 依赖后通过。

## 5. 可沉淀经验

- 已知数据例外必须绑定 Provider、运行模式、issue code、外部稳定 identity、精确 period 和基数，任一信息缺失都 fail closed。
- 汇总型质量 issue 只保存“第一个异常”时，不能仅凭该代表值做放行；必须携带足够的机器可读基数或完整集合。
- 环境收集失败不是有效 RED。有效 RED 必须进入约定 seam 并命中目标契约。
- 测试用参数表表达“一个允许、其余默认拒绝”，比重复测试函数更清晰，也更容易审查策略是否扩张。

## 6. 更好的初始提示词

> 在 MacroLens 的指定基线和独立 worktree 中，用 TDD 修复 TradingView USUR 历史发布门禁：只允许 `TRADINGVIEW_WEB` 的 `backfill` 在 `ECONOMICS:USUR` 恰好仅缺 `2025-10-01` 时把 `history_gap` 记为 warning；incremental、其他日期、其他 symbol、其他 Provider 或额外缺口必须 blocking。不要补造 null/value，不改 seed、registry、API、前端或部署。先在 `ingestion_issue_severity` 公共 seam 取得有效 RED，再让 completeness issue 携带精确 Provider identity 和缺口基数，传递 mode，跑定向与完整门禁，写结论报告并本地提交，不 push/merge/deploy。

## 7. 当前场景一次解决的更优方案提示词

> 从 `origin/master=f59bb60f6e60c5505df47cfd411a35d7fed422d2` 创建独立 worktree，先加载 MacroLens 组织规则和开发阶段 01 宪法。以参数化单测锁定一个 allow case：`TRADINGVIEW_WEB/backfill/history_gap/ECONOMICS:USUR/2025-10-01/missing_count=1 -> warning`；同一表中锁定 incremental、未知日期、未知 symbol、其他 Provider、`missing_count>1` 全部 blocking。实现时让 `CompletenessIssue` 携带 `provider_series_id` 与机器可读缺口数，history gap 创建时填充二者；严重级别函数接收 mode，使用代码内精确常量映射，并从任何通用 warning 分支排除 `history_gap`。禁止生产访问、伪造观测、seed/registry/API/前端改动、Docker 和部署。最后运行目标测试、completeness 测试、修改文件 Ruff、完整后端与 Web 六门禁、diff/范围检查，生成七节报告并提交清晰 commit，只返回 SHA 和证据。
