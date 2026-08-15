# ML-20260815-007 任务卡

- 任务 ID：`ML-20260815-007`
- 来源主线程：当前用户会话主线程
- 目标与业务场景：将本地冻结候选 `1974e8955e6b529a89fdfb3a7d73052d2c5e4453` 按 02→03 链路发布到 `ubuntu@111.229.152.122` 的独立 acceptance Compose，完成四源运行时验收，并向用户交付实际验证过的 Web/API 链接与验收账号密码。
- 成功标准：候选经 PR/CI 合并到 `master` 并创建不可变验收标签；服务器镜像可追溯到该标签/SHA；Compose 必需服务健康且 readiness/Web 200；长期 Scheduler 容器 ID、启动时间和重启次数不变；仅用一次性 Worker 执行 `audit-data` 与 BLS/BEA/Census/EIA `audit-live`；登录账号经真实 HTTP 登录、`/auth/me` 和退出闭环验证；最终报告不记录 Provider Key、JWT、数据库或对象存储秘密。
- 范围内：推送候选分支、创建和合并 PR、创建验收标签；服务器只读预检、源码/镜像发布、在不重建 Scheduler 的前提下更新必要的 Web/API/Worker 运行服务；一次性 Worker 审计；验收账号的受控确认或重置及登录验证；报告。
- 范围外：数据库 migration 执行、seed 执行、任何数据同步/backfill/发布、mapping 状态手工修改、真实 observation 写入、Scheduler 修改/停止/重启/重建、生产 Key 轮换或回显、删除容器/卷/数据、修改非 acceptance 栈。
- 分配部门席位：集成发布部 01（阶段 02 PRIMARY）、运维部 01（阶段 03 PRIMARY）、安全合规部 01与测试部 01（SUPPORTING）。
- 工作树与起始提交：运行时同源代理 remediation 使用 `E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-007-engineering-01`，起点 `1974e895`；阶段 02 使用该 remediation 的最终候选；阶段 03 仅使用服务器提交/标签源码，不在服务器编辑代码。
- 允许修改的模块：`apps/web/next.config.ts`、直接对应的同源代理回归测试、`.github/workflows/ci.yml` 的 Alembic 导入路径、对应静态回归测试、GitHub 分支/PR/标签；服务器 acceptance 发布目录、同项目镜像和允许更新的 Web/API/Worker 服务；本任务报告。不得修改根工作区用户既有文件。
- 公共接口或 Schema 影响：候选含既有 OpenAPI 及 Alembic/seed 定义；本任务允许发布代码但明确禁止执行 migration/seed。若运行库 Schema 不兼容，必须停止并回滚，不能绕过。
- 依赖任务：ML-20260815-003、ML-20260815-005、ML-20260815-006；现有项目 `macrolens-acceptance-20260814`、服务器四源 Key 与受限代理配置。
- 必须执行的检查：PR CI/审查；标签与合并 SHA 追溯；Compose 项目/镜像/端口/health/readiness；Scheduler 三元身份；一次性 Worker 残留；`audit-data`、四源 `audit-live`；审计前后 jobs/ingestion/raw/vintage/latest 零写快照；Web/API 登录、身份、数据页和退出；外部 HTTP 入口。
- 预期交付物：最终标签和 SHA、运行时链接、已验证账号密码、四源矩阵、零写/Scheduler 证据、回滚标识和七节结论报告。
- 阻塞时返回条件：CI/审查失败；必须执行 migration/seed/sync 才能启动；无法保持 Scheduler 不变；任一四源仍缺 verified mapping 或 live audit 失败；无法安全取得/重置验收账号；服务器或公网入口不可达。
