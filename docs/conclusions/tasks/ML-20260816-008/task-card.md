# ML-20260816-008 任务卡

- 任务 ID：`ML-20260816-008`
- 来源主线程：当前用户会话主线程；承接 `ML-20260815-007` 四源验收阻塞。
- 目标与业务场景：修复 BEA、BLS、Census、EIA 未全部生产接入，使四源均有真实官方响应验证的主映射，并在服务器一次性 Worker 的显式四源 `audit-live` 中执行且通过。
- 成功标准：四源 `executed=4`、`skipped=0`、`failed=0`；每源至少一条 `verified + primary` 映射及 MappingProbe/审批血缘；BLS 仅按官方脚注明确豁免 2025-10；Scheduler 身份、启动时间、重启次数不变；无 observation/run/raw 写入；readiness 与 Web 入口通过。
- 范围内：四源 Provider adapter、MappingProbe、完整性规则、必要 registry 元数据和测试；既有 Admin MappingProbe/审批流程；PR、CI、标签、服务器 API/Worker/Web 更新和一次性验收。
- 范围外：本地 Docker/Compose/服务容器；migration、seed、同步、backfill、observation 发布或删除；直接 SQL 强改 verified/primary；Scheduler 修改、重启或重建；泄露密钥、Token 或 Cookie。
- 分配部门席位：数据源部 PRIMARY；数据平台、研发、测试、安全合规、集成发布按阶段复核。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260816-008-data-sources-01`，基线 `97f20a839f4b53ca0b8bdd58d777682cd8d25954`。
- 允许修改的模块：`backend/src/macrolens_worker/providers/`、`backend/src/macrolens_worker/tasks/ingestion_quality.py`、对应测试、`database/seed/source_registry.json` 和本任务报告。
- 公共接口或 Schema 影响：无公共 API/OpenAPI/数据库 Schema 变更；若需要 migration 立即阻塞。
- 已验证根因：BLS 官方缺测脚注；EIA seriesid 兼容路由忽略 start/sort 但 offset 可定位历史边界；Census EITS 需获取矩阵后按完整维度过滤；BEA Real GDP 唯一 identity 为 `T10106/A191RX/Line 1`。
- 必须执行的检查：RED→GREEN 目标测试；根 AGENTS 六项门禁；diff/秘密检查；PR/CI；服务器 Compose、镜像、健康、readiness、Scheduler 不变、MappingProbe/审批、显式四源 audit 和零 observation 写证明。
- 阻塞时返回条件：官方 identity 不唯一；必须 migration/seed/sync；需重启 Scheduler；真实数据质量无法无伪造通过。
