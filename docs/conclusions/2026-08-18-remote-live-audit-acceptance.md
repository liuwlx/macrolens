# 远程验收 PostgreSQL Live Audit 结论

## 1. 连接方式

通过项目现有 SSH 只读链路连接服务器 `ubuntu@111.229.152.122`，发现实际健康数据库属于 Compose 项目 `macrolens-acceptance-20260814`，不是默认脚本匹配的 `macrolens` 项目。

- PostgreSQL：16.14；
- 数据库：`macrolens_acceptance_20260814`；
- Alembic：`0002_unique_primary_source`；
- SourceSeries：61 条；
- verified primary：14 条；
- SSH 本地隧道：15433，审计后已关闭。

没有启动、停止、迁移、seed 或修改数据库。

## 2. 远程增量审计结果

审计使用旧验收库中的 14 条 verified primary：

| Provider | 状态 | 结果 |
|---|---|---|
| BEA_API | passed | 1 个旧映射通过 |
| CENSUS_EITS_API | passed | 1 个旧映射通过 |
| BLS_API_V2 | failed | 5 个序列在 2025-10-01 缺值，质量门禁拒绝 |
| EIA_API_V2 | failed | 官方请求失败，当前响应触发压缩解码错误 |
| FRED_API | skipped | 旧验收库没有 verified primary |
| NYFED_MARKETS_API | skipped | 旧验收库没有 verified primary |
| US_TREASURY_XML | skipped | 旧验收库没有 verified primary |

总计：7 个 Provider，4 个执行，2 个通过，2 个失败，3 个跳过。

## 3. 重要边界

远程验收库还没有当前候选的 55 条新 READY 映射；当前候选 `source_registry.json` 的变化尚未 seed 到远程库。因此这次结果证明了远程连接和旧验收栈状态，不能宣称当前候选的 55 条指标已经完成生产验收。

EIA 失败需要单独处理 API key/官方响应压缩问题；BLS 缺值属于已知官方 2025-10 缺测，必须绑定官方脚注豁免或保持该批次 quarantine。两者都不能通过覆盖旧值绕过。

## 4. 后续解除条件

1. 集成当前候选提交；
2. 在独立验收 Compose 项目执行授权 migration/seed；
3. 重新建立 verified primary 和 source mapping；
4. 重新执行全量 incremental/backfill live audit；
5. 处理 BLS 官方缺值和 EIA 响应/密钥问题；
6. 通过后再进行远程 HTTP/业务验收。

上述 seed、迁移和部署属于数据库/服务器写操作，需要单独明确授权。
