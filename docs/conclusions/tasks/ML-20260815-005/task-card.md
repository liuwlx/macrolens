# ML-20260815-005 任务卡

- 任务 ID：`ML-20260815-005`
- 来源主线程：当前用户会话主线程
- 目标与业务场景：修复阻止四源 MappingProbe 候选进入集成的仓库基线门禁，形成可追溯的本地候选提交。
- 成功标准：FastAPI 路由面测试改为公共 OpenAPI seam；Python 3.12 环境下 ruff、mypy、pytest 全量通过；Node 22 环境下 Web lint、test、build 全量通过；生成候选 SHA 和完整证据。
- 范围内：`backend/tests/test_registry_and_schema.py`；全量 ruff/mypy 报告直接涉及的后端、测试、Alembic 配置或精确 lint/type 配置；仅在 Web 门禁暴露真实源码错误时修改对应 Web 文件；本任务报告。
- 范围外：MappingProbe 候选代码；公共 API/Schema；registry、映射审批、生产 Key；迁移执行、seed、数据库同步、真实 Probe、Scheduler；合并、推送、标签和部署。
- 分配部门席位：研发部实现席位 01；主线程负责验收与移交。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-005-engineering-01`，起始提交 `aa739273710358e5f84efe724554df13efe4d3ea`。
- 允许修改的模块：上述范围内文件；不得回退或覆盖根工作区现有用户变更。
- 公共接口或 Schema 影响：无；测试只改用既有 OpenAPI 公共契约。
- 依赖任务：`ML-20260815-004` 诊断；后续由集成发布部与 `ML-20260815-003` 候选整合。
- 必须执行的检查：`ruff check backend`、`mypy backend/src`、`pytest backend/tests`、`npm --workspace apps/web run lint`、`npm --workspace apps/web run test`、`npm --workspace apps/web run build`，以及 `git diff --check`。
- 预期交付物：实现提交 SHA、六门禁原始摘要、工具链版本、变更清单、风险说明和七节结论报告。
- 阻塞时返回条件：Node 22 或依赖无法获得；全量错误需要公共 API/Schema、生产环境或数据库状态变更；发现用户现有改动与修复冲突。
