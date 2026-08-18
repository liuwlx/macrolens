# 远程验收库 Migration / Seed 结论

## 1. 授权与目标

用户明确授权：在 `macrolens-acceptance-20260814` 验收 Compose 项目执行 migration/seed，并使用当前候选版本更新验收库。

## 2. 执行环境

- 服务器：`ubuntu@111.229.152.122`；
- Compose 项目：`macrolens-acceptance-20260814`；
- PostgreSQL：16.14；
- 数据库：`macrolens_acceptance_20260814`；
- Alembic 迁移前后：`0002_unique_primary_source`；
- 连接方式：临时 SSH 隧道 `127.0.0.1:15433 → PostgreSQL 容器内网 172.22.0.2:5432`；
- 隧道：执行结束后已关闭。

## 3. 执行结果

### Migration

`alembic upgrade head` 成功，事务性 DDL 正常，无新增 migration 需要应用。

### Seed

当前候选 `backend/src/macrolens_api/cli.py seed` 成功，输出 `Seed completed.`。本轮修复了一个真实兼容问题：注册表使用 `FED_BOARD_FILES`，seed Provider 元数据此前只有 `FEDERAL_RESERVE`；已补充 Federal Reserve Board Release Files Provider 元数据后重新测试并成功 seed。

## 4. Seed 后远程只读核对

- Catalog Series：61；
- active Series：55；
- draft Series：6；
- SourceSeries：69（部分指标保留多个来源映射）；
- Provider：15；
- Dataset：30；
- TaxonomyNode：64；
- TaxonomySeries：61；
- observation_latest：1,398；
- mapping_status：verified 14、needs_review 51、license_required 4；
- `FED_BOARD_FILES` Provider：已存在；8 条 Fed Board source mapping 已写入。

重要：seed 对 `mapping_status=READY` 的新候选映射按设计写成 `needs_review`，不会伪造 `verified` 或 `is_primary`。当前 51 条 needs_review 必须经过 mapping probe/approval 后，才能进入生产同步和完整 live audit。

## 5. Seed 后只读 Live Audit

对旧验收库中已有的 14 条 verified primary 重跑增量 audit：

- BEA：通过；
- Census：通过；
- BLS：失败，5 条序列的 2025-10 官方缺值触发质量门禁；
- EIA：失败，官方响应返回 403，并触发压缩解码错误；
- FRED、NY Fed、Treasury：跳过，当前库没有 verified primary。

本结果不能代表当前 55 条新映射已经完成 live audit，因为它们仍是 needs_review；完整结果见 [live-incremental-audit-after-seed.json](./2026-08-18-live-incremental-audit-after-seed.json)。

## 6. 未执行

- 未执行生产同步或 backfill；
- 未启动/重启 Compose；
- 未修改 observation/vintage；
- 未部署新的候选镜像；
- 未手工把 needs_review 改成 verified/primary；
- 未处理商业许可证或两个 BEA 派生公式。

## 7. 后续动作

1. 对 51 条 needs_review 映射执行 mapping probe，并通过审批流程产生 verified primary；
2. 重新执行当前候选 55 条的 incremental/backfill live audit；
3. 处理 BLS 2025-10 官方缺值证据和 EIA API/密钥问题；
4. 通过后再授权生产同步、部署和远程业务验收。
