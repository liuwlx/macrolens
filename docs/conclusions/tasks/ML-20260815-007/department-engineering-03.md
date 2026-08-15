# ML-20260815-007｜研发部 04 结论报告

## 1. 问题与场景

PR #11 在 acceptance 前审查中确认四个 P1：CI checkout 中 `scripts/wait_for_http.sh` 的 Git mode 为 `100644`，直接执行会失败；observation raw replay 查询没有包含 `vintage_at`，会把同 raw/source/period 的后续 vintage 错判为 exact replay；EIA Probe 对 `min_observations_backfill` 缺失、非法和过小配置回退到 1 且在网络后才处理；EIA/Census Probe 从未脱敏的 JSON payload 构造 description/evidence，success-like 上游响应可回显当前 API key。任务要求在独占 worktree 中以 RED→GREEN 修复，不修改 `next` 默认地址，不运行 Docker、数据库、Alembic、migration、seed、sync、真实 Probe 或 Scheduler，也不 push。

## 2. 分析过程

事实与结论如下：

- CI workflow 有三处 `./scripts/wait_for_http.sh`，而任务确认脚本 mode 为 `100644`；显式交给 `bash` 可消除执行位依赖，且无需修改 mode。
- `_merge_observation` 的首个查询只使用 source、period、raw object。raw object 可包含同一 period 的多个 point-in-time vintage，因此该键不足以表示 exact replay；加入 `vintage_at` 后才与不可变 vintage 身份一致。
- EIA 的 `or 1` 与异常回退 1 同时掩盖缺失、非法和小于安全下限的配置，而且解析位于 HTTP 响应后；固定配置必须先于网络验证。
- EIA/Census 已有 `_redact_sensitive_data` 递归工具，但 Probe 解析仍读取原 payload；SHA 应继续绑定原始 bytes，而 description、headers、dimensions、value 和 evidence 应只读取脱敏副本。
- 全量 pytest 首轮还发现一个预期 PASS 的 EIA fixture 未声明新强制下限。生产规则不能为旧 fixture 放宽；用户扩展所有权后，只给该 fixture 增加 `min_observations_backfill=100`。
- Windows 默认 GBK 导致两个无关 UTF-8 文件读取测试失败；`PYTHONUTF8=1` 后消失。Web 首轮用 Node 20 启动 Vitest 时出现 CJS/ESM loader 错误；将子进程 PATH 固定为 CI 同代 Node 22 后通过。这两项均为验证环境问题，不是产品缺陷。

## 3. 解决流程

1. 建立五个确定性、无网络/无数据库反馈环：CI 静态调用、不同 vintage 的 raw replay SQL/行为 seam、EIA 配置前置门禁、EIA success-like secret 回显、Census success-like secret 回显。
2. 在生产代码修改前逐项取得 RED：CI 断言未显式 `bash`；不同 vintage 返回 `unchanged` 而非插入；三类 EIA 错误配置仍发 HTTP；EIA/Census 结果递归 secret 哨兵失败。
3. 最小实现：三处改为 `bash scripts/wait_for_http.sh`；raw replay 查询加入 `ObservationVintage.vintage_at == observation.vintage_at`；EIA 在网络前将固定下限解析为整数并要求 `>=2`；EIA/Census 在字段解析前递归脱敏 `response.json()`，原始 bytes SHA 计算保持不变。
4. 运行目标测试并确认 `77 passed`；exact replay 仍一次查询返回 `unchanged`，不同 vintage 继续插入。
5. 对扩展 fixture 先取得单例 RED，再只补 `min_observations_backfill=100`，单例 GREEN 后以 `PYTHONUTF8=1`、`PYTHONPATH=backend/src` 运行全量后端测试，结果 `236 passed`。
6. 同步根任务卡与 worktree 副本，保留扩展允许模块；检查 diff、文件范围、Git mode、秘密哨兵和最终工作区状态后提交。

## 4. Agents、skills、tools 与文档

- Agent：研发部 04 当前 Codex 线程；未创建或调用其他子 Agent。
- Skill：`diagnosing-bugs`。它要求先建立可重复、可独立运行且能命中具体症状的反馈环，再进行假设、最小修复和回归；本次 RED→GREEN 顺序与 secret 输出脱敏受该 skill 约束。
- Tools：`shell_command` 用于只读检查和测试门禁；`apply_patch` 用于所有仓库文件修改；`update_plan` 用于阶段跟踪；`wait` 用于等待依赖安装和长测试完成。
- 已读规则与文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、根与 worktree 任务卡、`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`、`02-pr-merge-and-release.md`、`diagnosing-bugs/SKILL.md`，以及本次所有权内实现和测试文件；未发现相关 `CONTEXT.md` 或 ADR。
- 开发链路阶段：实际执行阶段 01，本地修复、测试与候选冻结；阅读阶段 02 是因为任务关联 PR #11，但本席位未 push、合并或打标签。阶段 01 证据为目标 `77 passed`、ruff/mypy、后端全量 `236 passed`、Web lint/test/build 与最终 diff 检查；阶段 02 未执行任何外部写操作。

## 5. 值得沉淀的经验与模式

- “同一 raw”不是 observation replay 的完整身份。幂等键必须覆盖所有不可变身份字段；对 vintage 数据至少包含 source、period、raw object 和 `vintage_at`。
- Provider Probe 应采用“原始证据哈希、脱敏副本解析”的双轨模式：原始 bytes 只用于不可变 SHA，任何可持久化或可展示字段只从递归脱敏副本读取。
- 配置型 fail-closed 必须位于网络边界之前，且不能用宽松默认值掩盖缺失配置。测试应同时断言 classification、configuration issue、空 SHA 和 HTTP handler 未调用。
- 新增强制映射字段时，应搜索所有 PASS fixtures 和 registry 示例；负向测试转绿并不代表仓库中所有正向 fixture 已同步。
- 跨平台门禁需要固定解释器语义：Windows 后端测试显式使用 UTF-8，前端测试确保 npm 子进程也使用 Node 22，而不只让父 npm CLI 使用 Node 22。

## 6. 更好的初始提示词

> 请审查并修复 PR #11 中四个高优先级问题：CI 中不可执行的 HTTP 等待脚本、同一原始数据下不同 observation vintage 被误判为重复、EIA 回填最小观测数配置未在联网前严格校验，以及 EIA/Census Probe 可能把 API key 回显到结果。请先为每个问题写能稳定失败的离线回归测试，再做最小修复；保持原始响应 SHA 不变、exact replay 幂等和 Provider 身份 fail-closed。搜索并同步所有受新强制配置影响的预期 PASS 测试 fixture。最后运行 Python 3.12/UTF-8 后端全量测试、ruff、mypy，以及 Node 22 下 Web lint/test/build；不要运行 Docker、数据库、迁移、seed、sync、真实 Probe 或 Scheduler，不要 push。

## 7. 更优的一次解决方案提示词

> 在独占 worktree 从指定 clean HEAD 修复 PR #11 的四项 P1，并一次完成依赖面核对。第一步读取项目规则、任务卡和开发宪法；第二步用代码搜索列出所有 `wait_for_http.sh` 调用、raw replay 查询、EIA `min_observations_backfill` 使用点、EIA/Census Probe payload 解析点，以及所有 EIA PASS fixture；第三步逐项新增离线 RED 测试并记录失败；第四步最小修复：workflow 三处显式 bash、replay 键加入 vintage_at、EIA 固定整数下限在 HTTP 前要求 >=2、Probe 采用“原始 bytes 算 SHA + 当前 key 递归脱敏副本做解析”，并同步所有正向 fixture；第五步运行目标测试和完整六门禁，Windows 后端设置 `PYTHONUTF8=1`/`PYTHONPATH=backend/src`，Web 使用 Node 22；第六步做范围、mode、secret、diff 检查，写七节报告并提交，不 push。任何生产规则不得为了旧测试放宽。
