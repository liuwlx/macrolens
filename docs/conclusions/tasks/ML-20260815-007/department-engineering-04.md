# ML-20260815-007｜GitHub acceptance 干净 seed 映射契约修复

## 1. 问题与场景

PR #11 的 GitHub 远程 acceptance 作业在 `seed-test-fixtures` 阶段失败。干净 catalog seed 按安全规则将 Registry 中 READY 映射初始化为 `needs_review`，只有真实 Probe 审批后才允许成为 `verified`；旧验收夹具却只查询 `verified + is_primary`，因此新数据库必然少于三条可用映射。该故障发生在 GitHub 临时 Runner，不是目标服务器故障。

## 2. 分析过程

先以远程失败日志建立反馈回路，精确定位 `test_fixtures.py` 的“至少三条 verified 映射”异常；再比对 `cli.seed_all()` 的 Probe 审批保留逻辑和 acceptance fixture 查询条件。排除 EIA 回填窗口、Registry READY 数量不足和状态枚举拼写问题后，确认根因是 2026-08-13 引入的 fail-closed seed 语义与旧 fixture 前置条件不兼容。另确认 Windows 本机 Node 20 不满足仓库 `node >=22`，以及 Python 默认 GBK 会导致两个 UTF-8 fixture 读取测试失败；这两项通过匹配项目运行环境处理，没有修改业务代码。

## 3. 解决流程

1. 新增最小回归，模拟三条干净 seed 后的 `needs_review` 映射，先观察缺少 fixture 审批函数的 RED。
2. acceptance fixture 改为选择 active 且状态为 `needs_review/verified` 的映射，不选择 disabled 或 license-required 映射。
3. 对尚未验证的候选创建显式、test-only 的成功 MappingProbe Job 证据，并复用生产审批服务写入审批血缘；不恢复 Registry 自动信任。
4. 将门禁收紧为仅 `ENVIRONMENT=test` 且 `ALLOW_TEST_FIXTURES=true`；普通 development、staging 和 production 全部拒绝。目标服务器不执行 `seed-test-fixtures`。
5. 修复旧结论报告的 EOF 空行，完成目标回归、类型检查和六项工程门禁。

## 4. Agents、skills、tools 与文档

- Agents：当前主线程完成故障闭环；本轮没有启用新的部门子 Agent。既有候选的研发、质量和双轴代码审查证据保留在同任务目录的 01～03 报告中。
- Skill：`diagnosing-bugs`，用于建立远程日志→最小本地回归→RED/GREEN→完整门禁的证据链，并约束敏感信息脱敏。
- Tools：PowerShell 只读检查和 Python/Node 测试；`apply_patch` 修改代码与报告；Git/GitHub CLI 检查 PR 与 CI；计划工具维护阶段状态。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、开发宪法索引及 01/02/03、任务卡、`backend/src/macrolens_api/cli.py`、`test_fixtures.py`、映射审批服务、GitHub CI 失败日志。
- 执行阶段：01 候选修复与冻结；02 等待新提交和 CI。阶段 03 尚未开始。全程未在本地启动 Docker/Compose/服务容器，也未执行数据库、migration、seed、sync、真实 Probe 或 Scheduler 操作。

## 5. 值得沉淀的经验与模式

fail-closed 的生产 seed 与运行时验收夹具必须分别定义信任来源：生产 Registry 不能自动成为 verified；临时验收数据又必须拥有可查询的审批血缘。最稳妥的模式是在强 test-only 门禁内生成明确标记的合成 Probe 证据，并复用同一个审批入口，而不是绕过状态机直接改字段。门禁还必须使用项目声明的 Node/Python 版本与 UTF-8 模式，否则环境错误会掩盖真实回归。

## 6. 更好的初始提示词

> PR 的 GitHub acceptance 在干净数据库执行 `seed-test-fixtures` 时提示“至少需要三条 verified source mappings”。请先核对 catalog seed 是否按安全规则把 READY 映射置为 needs_review，再为该冲突写最小 RED 测试。只允许在 `ENVIRONMENT=test + ALLOW_TEST_FIXTURES=true` 下创建带显式 fixture 标记的 MappingProbe 审批血缘，禁止恢复 Registry 自动信任，禁止本地 Docker，完成六项门禁后推送原 PR。

## 7. 当前场景的一次性更优方案提示词

> 在独立 worktree 中读取 AGENTS、组织规则和 01→03 宪法，针对 PR acceptance 的干净 seed 失败直接检查 `seed_all()` 与 `seed_runtime_acceptance_fixtures()` 的状态契约。用纯 Python 测试复现三条 needs_review 映射无法进入运行时夹具；实现 test-only 合成 Probe Job 并调用生产 `approve_mapping_from_probe`，候选查询仅允许 active 的 needs_review/verified，保留双重环境开关。用 Python 3.12 UTF-8 和 Node 22 跑完整六门禁，diff/security/Scheduler 范围检查后提交推送并等待四个 GitHub jobs 全绿；全程不在本地运行容器，也不触碰目标服务器 migration、seed、sync、映射或 Scheduler。
