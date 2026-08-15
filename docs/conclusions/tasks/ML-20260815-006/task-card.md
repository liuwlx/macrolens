# ML-20260815-006 任务卡

- 任务 ID：`ML-20260815-006`
- 来源主线程：当前用户会话主线程
- 目标与业务场景：把已通过六项基线门禁的候选 `6b0cbd8d48c0b049b65c664c379606db09bfde87` 与完整四源 MappingProbe 候选 `a16f2ca99e2102862d95a515c07429d6354adbb4` 整合为一个可追溯、可复测的本地生产前候选。
- 成功标准：完整保留 `a16f2ca` 自共同基线 `aa739273710358e5f84efe724554df13efe4d3ea` 起的依赖链；冲突解决不削弱 MappingProbe 的 fail-closed、安全脱敏、响应指纹和审计语义；定向测试与根 `AGENTS.md` 六项门禁全部通过；Scheduler 内容相对两个输入候选均无新增修改；形成唯一候选 SHA 和七节结论报告。
- 范围内：本地独立集成 worktree；两个冻结候选的本地合并、冲突解决、必要的最小兼容修复、定向测试、六项门禁和报告。
- 范围外：推送远程、创建/合并 PR、修改 `master`、打标签、部署、启动 Docker/Compose、读取或轮换生产 Key、真实 Provider Probe、mapping approve、数据库迁移执行、seed 执行、数据库同步/backfill，以及任何 Scheduler 修改或重启。
- 分配部门席位：集成发布部席位 01；主线程负责验收与移交。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-006-integration-release-01`，起始提交 `6b0cbd8d48c0b049b65c664c379606db09bfde87`。
- 允许修改的模块：合并冲突涉及文件、为保持两个候选契约所需的最小兼容修复、本任务报告；不得回退或覆盖根工作区现有用户变更。
- 公共接口或 Schema 影响：不新增超出 `a16f2ca` 完整依赖链的公共接口或 Schema 变化。该依赖链包含既有 Alembic 迁移文件和 seed 定义变更，本任务只纳入代码历史，禁止执行；部署前必须另行审查和授权。
- 依赖任务：`ML-20260815-002`、`ML-20260815-003`、`ML-20260815-005`；输入候选分别为 `a16f2ca` 与 `6b0cbd8`。
- 必须执行的检查：MappingProbe/审计相关定向 pytest；`ruff check backend`、`mypy backend/src`、`pytest backend/tests`、`npm --workspace apps/web run lint`、`npm --workspace apps/web run test`、`npm --workspace apps/web run build`、`git diff --check`。
- 预期交付物：本地集成提交 SHA、完整提交来源、冲突与解决记录、测试原始摘要、迁移/seed 未执行证明、Scheduler 零修改证明、风险说明和七节结论报告。
- 阻塞时返回条件：需要丢弃任一候选的安全/数据契约；需要实际迁移、seed、数据库同步、Provider Probe、生产 Key 或 Scheduler 操作才能使门禁通过；发现输入候选历史不完整或不可追溯。
