# ML-20260815-007 任务卡

- 任务 ID：`ML-20260815-007`
- 来源主线程：当前用户会话主线程；PR #11 审查整改。
- 目标与业务场景：研发部 04 在独占 worktree 内以 RED→GREEN 修复四个已确认 P1：CI 对 mode `100644` readiness 脚本的调用、raw replay vintage 键、EIA Probe 固定回填下限门禁，以及 EIA/Census Probe success-like 响应中的 API key 递归脱敏和 fail-closed。
- 成功标准：三处 readiness 等待均显式经 `bash` 调用且有静态回归；same raw/source/period 的不同 `vintage_at` 不早退、exact replay 保持幂等；EIA `min_observations_backfill` 缺失/非法/小于 2 时在 HTTP 前 BLOCKED；EIA/Census Probe 对解析证据使用递归脱敏 payload、SHA 仍基于原始 bytes、污染身份字段时 fail-closed；目标测试 GREEN，并执行完整工程门禁和 diff 检查。
- 范围内：`.github/workflows/ci.yml`、`backend/src/macrolens_worker/tasks/sync.py`、`backend/src/macrolens_worker/providers/eia.py`、`backend/src/macrolens_worker/providers/census.py`、`backend/tests/test_static_invariants.py`、`backend/tests/test_m0_bls_cpi.py`、`backend/tests/test_mapping_probes.py`、`backend/tests/test_probe_mapping.py` 中预期 PASS 的 EIA locator fixture、本任务卡副本与 `department-engineering-03.md`；同步根工作区同名任务卡。
- 范围外：修改 `apps/web/next.config.ts` 默认地址；Docker、Compose、本地或远程数据库、Alembic、migration、seed、sync、真实 Probe、Scheduler；push、merge、标签、部署；回退其他工作者提交；修改未授权文件。
- 分配部门席位：研发部 04（PRIMARY）。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-007-engineering-01`，clean HEAD `e194a6d2761b8442c7aace188af68806933bd3a3`，关联 PR #11。
- 允许修改的模块：仅“范围内”列出的文件；不得修改脚本本地 Git mode。
- 公共接口或 Schema 影响：无公共 API、OpenAPI、数据库 Schema、migration 或 seed 变更。
- 依赖任务：PR #11 当前候选与四项 P1 审查结论；根组织规则和开发链路宪法 01/02。
- 必须执行的检查：每项回归先 RED 后 GREEN；目标三文件 pytest；`ruff check backend`；`mypy backend/src`；`pytest backend/tests`；`npm --workspace apps/web run lint`、`test`、`build`；`git diff --check`、mode/范围/敏感信息检查。
- 预期交付物：四项最小修复、回归测试、同步任务卡、七节研发结论报告、单一提交 SHA、最终 clean 状态；不 push。
- 阻塞时返回条件：必须越权修改文件才能恢复完整门禁；必须使用 Docker/数据库/迁移/同步/真实 Probe/Scheduler；发现与其他工作者变更冲突；发现秘密或不可接受的数据兼容风险。
