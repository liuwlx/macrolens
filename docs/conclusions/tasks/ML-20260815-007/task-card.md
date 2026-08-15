# ML-20260815-007 任务卡

- 任务 ID：`ML-20260815-007`
- 来源主线程：当前用户会话主线程；PR #11 审查整改。
- 目标与业务场景：完成 PR #11 的发布前整改与运行时验收。除既有 Probe、vintage replay、Web 代理和 CI 修复外，以 RED→GREEN 修复 GitHub 临时 acceptance 的干净 seed 映射血缘、任意首项序列修订夹具、AI 缺省快照时间和 Playwright project 参数转发问题。
- 成功标准：既有 P1 保持通过；临时 acceptance fixture 只在显式 test 双开关下建立 fixture Probe 审批血缘并让每个入选序列具备修订数据；AI 缺省 cutoff 精确复用请求开始时间；Chromium project 参数到达最终 Playwright；不得恢复 Registry 自动信任；目标测试、完整工程门禁、diff check 和 GitHub CI 全绿。
- 范围内：既有候选变更；`backend/src/macrolens_api/test_fixtures.py`、`backend/src/macrolens_api/routers/ai.py`、`backend/tests/test_runtime_acceptance_fixtures.py`、`backend/tests/test_data_browser.py`、`.github/workflows/ci.yml`、`apps/web/next.config.ts`、`apps/web/e2e/critical-path.spec.ts`、`apps/web/e2e/data-browser-demo.spec.ts` 及对应测试、任务卡和七节结论报告；阶段 02 的 push/PR/merge/tag 与阶段 03 的目标服务器部署和验收。
- 范围外：本地 Docker/Compose/服务容器；目标服务器 migration、seed、数据同步/回填、映射手工修改；Scheduler 修改、重启或重建；回退其他工作者提交；输出 Provider 密钥、哈希、Token 或 Cookie。
- 分配部门席位：研发部 04（PRIMARY）。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-007-engineering-01`，clean HEAD `e194a6d2761b8442c7aace188af68806933bd3a3`，关联 PR #11。
- 允许修改的模块：仅“范围内”列出的文件；不得修改 readiness 脚本本地 Git mode。
- 公共接口或 Schema 影响：本次增量无新的公共 API/OpenAPI/Schema；PR 全候选包含既有 migration `0002_unique_primary_source`、模型验证字段和 Registry seed 变更。目标服务器禁止执行 migration/seed，故 Stage 03 前必须只读证明目标库已处于兼容版本，否则阻塞并回滚应用发布。
- 依赖任务：PR #11 当前候选、审查结论、GitHub acceptance 失败日志；根组织规则和开发链路宪法 01/02/03。
- 必须执行的检查：回归先 RED 后 GREEN；相关 pytest；`ruff check backend`；`mypy backend/src`；`pytest backend/tests`；`npm --workspace apps/web run lint`、`test`、`build`；`git diff --check`、mode/范围/敏感信息检查；GitHub CI；服务器 Compose/镜像/健康/readiness/UI/一次性 Worker 审计证据。
- 预期交付物：修复提交与 PR、合并提交、不可变标签、服务器运行时验收、一次性 Worker 四源审计、七节结论报告、最终验收链接和已验证账号密码。
- 阻塞时返回条件：修复需要恢复 Registry 自动信任或降低 Probe 门禁；目标服务器需要 migration/seed/sync/映射状态变更；必须重启 Scheduler；发现秘密泄漏、数据兼容风险或无法无迁移部署。
