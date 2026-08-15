# ML-20260815-002｜研发部 IMPLEMENTING 结论报告

- 席位状态：`REVIEW`
- 起始提交：`a34901c14337a66fdf523da583205f776758a577`
- 执行阶段：01 本地开发与候选冻结
- 范围：仅修改 live audit 汇总、对应测试和本报告；未修改 CLI 文件，因为既有 CLI 已以 `all_executed_passed` 判定退出码。

## 1. 问题与场景

`audit_live_data()` 原先从 verdict 中排除所有 `skipped` 报告。显式请求多个 Provider 时，只要至少一个已执行 Provider 为 `passed`，其余请求项即使因 `no_verified_mappings` 被跳过，`all_executed_passed` 仍会错误为 `true`，使 `python -m macrolens_worker.main audit-live` 退出 0。显式请求表达的是“这些 Provider 都必须接受审计并通过”，因此 skipped 不应被忽略。

## 2. 分析过程

先核验指定 worktree、干净分支和起始 SHA，再读取组织规则、任务卡及测试部/数据平台部报告。该候选基线不包含 `docs/governance/development-constitutions/`，所以只读加载了根 worktree 中的宪法索引与阶段 01 文件；未对根 worktree 写入。

公共 seam 已由任务明确确认：`audit_live_data()` 汇总和 Typer `audit-live` 命令。现有代码的 `executed` 集合排除了 skipped，CLI 又只读取 `all_executed_passed`，由此定位到一个汇总层条件错误。为保持兼容性，未请求 Provider 的全量审计仍沿用“只评价 executed、忽略 intentionally skipped”的旧语义；只有显式请求时改为评价全部返回报告。

有效 RED：

```text
$env:PYTHONPATH='backend/src'; python -m pytest backend/tests/test_live_audit.py::test_explicit_audit_fails_when_one_requested_provider_is_skipped -q
FAILED ... assert True is False
1 failed
```

此前两次尝试不计为 RED：一次因缺少 `pytest-asyncio` 被 skipped；一次因缺少 `boto3` 在导入阶段失败。测试随后用标准库 `asyncio.run()` 驱动，并按仓库既有方式隔离与本票无关的对象存储导入边界。

## 3. 解决流程

1. RED：构造显式 `passed + skipped`，确认旧实现错误返回 true。
2. GREEN：显式请求时用全部 `provider_reports` 计算 verdict；未显式请求时继续用 `executed`。
3. 逐片补齐显式 all-passed、missing、fetch-failed、未过滤兼容语义。
4. 通过真实 `CliRunner` 调用 `audit-live`，覆盖 mixed=5、missing=5、failed=5、all-passed=0。
5. 运行相关测试、Python 3.12 compileall、`git diff --check` 和根规则六条全量门禁；环境缺失项如实记录。

GREEN 证据：

```text
$env:PYTHONPATH='backend/src'; python -m pytest backend/tests/test_live_audit.py -q
......... [100%]
9 passed, 1 warning in 5.43s

py -3.12 -m compileall -q backend/src/macrolens_worker/live_audit.py backend/tests/test_live_audit.py
exit 0

git diff --check
exit 0（仅 Git 提示未来可能进行 LF→CRLF 转换）
```

警告来自系统 pytest 7.4.3 不识别项目 `asyncio_mode`；本文件的用例没有被跳过。

## 4. Agents、skills、tools 与文档

- Agent：研发部 IMPLEMENTING 席位；未调用其他 Agent。
- Skill：`tdd`，按公共 seam 执行 RED→GREEN 纵向切片，并遵循其 `tests.md`、`mocking.md`。
- Tools：PowerShell、`rg`、Git、`apply_patch`、pytest、Typer `CliRunner`、Python 3.12 `compileall`、npm 门禁命令。
- 已读项目文档：worktree `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`；根 worktree 的开发宪法索引与 `01-local-development-and-freeze.md`（候选基线内缺失）；任务卡、测试部报告、数据平台部报告。
- 已读代码/测试：`live_audit.py`、Worker `main.py`、`ingestion_quality.py`、`test_ingestion_completeness.py` 相关 live-audit 用例及测试配置。
- 阶段验收：独立 worktree、起始 SHA、相关测试和候选提交均已形成；未启动 Docker、未连接或修改远程服务、未进入 PR/发布/部署阶段。

## 5. 值得沉淀的经验

1. “所有已执行项通过”与“所有显式请求项通过”是不同集合命题；显式筛选接口必须把 skipped 当作未满足请求。
2. 兼容性应按调用模式区分：全量审计可继续展示并忽略 intentionally skipped，显式审计则应严格失败。
3. CLI 不需要重复实现 Provider 状态判断；汇总层提供可靠 verdict 后，既有单一退出判定即可保持一致。
4. skipped 测试或依赖导入失败不是行为 RED，必须取得目标断言失败后才进入 GREEN。

## 6. 更好的初始提示词

> 在独立 worktree 中修复 Worker `audit-live`：当命令显式传入多个 `--provider` 时，只有每个请求 Provider 都返回 `passed` 才允许退出 0；任何 `skipped`、missing 或 fetch failed 都退出 5。保持未传 `--provider` 的全量审计旧语义。请先用 `audit_live_data()` 的 mixed passed/skipped 公共 seam 写失败测试，再做最小修改，并用 Typer `CliRunner` 覆盖 mixed=5、all-passed=0、missing/failed=5。不要修改 registry、seed、adapter、数据库、Scheduler、部署配置或服务器。

## 7. 更优方案反思与提示词

当前方案已是更优的最小修复：不新增返回字段、不改 CLI、不触碰 Provider 业务层，只把 verdict 的评价集合与调用者意图对齐。更大的重命名或新增 `all_requested_passed` 会扩大公共报告契约并增加集成成本，不适合本票。

> 基于当前 `audit_live_data()` 返回契约做一个条件化 verdict 修复：`provider_codes` 非空时，`all_executed_passed` 对全部请求报告执行 `bool(reports) and all(status == 'passed')`；未指定时继续对非 skipped 的 executed 报告计算。以真实汇总函数和 Typer CLI 为两个公共 seam，测试 explicit mixed、explicit all passed、missing、fetch failed 和 unfiltered compatibility；仅在这些测试红后改一处生产逻辑，完成后提交单一候选 commit，并记录环境阻塞的全量门禁原始错误。

## 全量门禁与集成说明

- `ruff check backend`：未运行成功，`ruff` 命令不存在。
- `mypy backend/src`：未运行成功，`mypy` 命令不存在。
- `pytest backend/tests`：收集失败；系统为 Python 3.11.9/pytest 7.4.3，项目包未安装且未设置 `PYTHONPATH`，16 个模块报 `ModuleNotFoundError: macrolens_api/macrolens_worker`。
- `npm --workspace apps/web run lint`：失败，`eslint` 不存在。
- `npm --workspace apps/web run test`：失败，`vitest` 不存在。
- `npm --workspace apps/web run build`：失败，`next` 不存在。
- 未继续安装大型依赖，符合用户收口指令。
- 风险：返回字段名 `all_executed_passed` 在显式模式下现在代表“全部请求项通过”，名称不完全精确，但保持了 JSON/CLI 契约兼容。未过滤模式已有专门回归测试。
- 集成发布部可直接 cherry-pick 本报告所列提交；无需修改 CLI 文件、数据库、registry、seed、adapter 或部署配置。集成环境应使用 Python 3.12 完整依赖重跑根规则六条门禁。
