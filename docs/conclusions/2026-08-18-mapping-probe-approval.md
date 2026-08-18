# 远程 MappingProbe / Approval 结论

## 1. 执行范围

用户授权后，在 `macrolens-acceptance-20260814` 验收 PostgreSQL 上，对 seed 后 `active + needs_review` 的 SourceSeries 执行当前候选代码的 MappingProbe。每条 probe 先创建 `mapping_probe` Job 并保存官方证据；只有 `production_ready=true`、`classification=PASS`、身份/授权/指纹一致时，才调用原子 `approve_mapping_from_probe` 晋级 `verified/primary`。

## 2. 执行结果

- eligible：49 条；
- approved：37 条；
- probe blocked：12 条；
- seed 后远程状态：verified/primary 51 条，needs_review 14 条，license_required 4 条。

已晋级的 37 条使用 `verified_by=codex-authorized-mapping-audit`，每条都绑定了不可变 MappingProbe Job 和 mapping fingerprint。没有直接修改 verified 状态，也没有绕过 approval service。

## 3. 仍然阻塞的 12 条

| SourceSeries | 指标 | Provider | 结果 |
|---:|---|---|---|
| 36 | US.JOB.OPENINGS | BLS_API_V2 | business error |
| 45 | US.TREASURY.2Y | US_TREASURY_XML | transport error |
| 46 | US.TREASURY.10Y | US_TREASURY_XML | transport error |
| 47 | US.REAL.10Y | US_TREASURY_XML | transport error |
| 62 | US.INDUSTRIAL.PRODUCTION | FED_BOARD_FILES | transport error |
| 63 | US.FED.ASSETS | FED_BOARD_FILES | transport error |
| 64 | US.FED.MBS | FED_BOARD_FILES | transport error |
| 65 | US.DOLLAR.INDEX | FED_BOARD_FILES | transport error |
| 66 | US.BANK.CREDIT | FED_BOARD_FILES | transport error |
| 67 | US.CONSUMER.CREDIT | FED_BOARD_FILES | transport error |
| 68 | US.CARD.DELINQUENCY | FED_BOARD_FILES | transport error |
| 69 | US.SLOOS | FED_BOARD_FILES | transport error |

这些失败没有晋级，保留为 `needs_review`。Fed Board/Treasury 失败发生在当前本机 probe 网络路径；此前这些官方文件曾在直连只读验证中成功，不应据此修改身份或覆盖数据。

## 4. 代码修复

- 将 `FED_BOARD_FILES` 加入 MappingProbe Adapter Registry；
- 为 Federal Reserve Board Adapter 增加 G.17/XML ZIP probe，包含 HTTP、原始 SHA-256、Series/属性/历史边界和观察数量证据；
- 新增 Fed probe fixture；
- 相关提交：`7a77164`、`175e76c`。

## 5. 测试

- MappingProbe/Fed 目标测试：73 passed；
- 后端全量：269 passed，5 warnings；
- ruff：通过；
- mypy：通过；
- Node 22 Web test：35 passed；
- Web lint/build：通过。

## 6. 未执行

- 未执行 observation sync/backfill；
- 未覆盖旧 vintage；
- 未部署或重启 Compose；
- 4 条许可证数据仍保持 license_required；
- 两个 BEA 派生概念仍保持 needs_review。

## 7. 下一步

先解决 Fed Board/Treasury 的远程网络出口或让服务器 Worker 执行 probe，再重试 11 条 transport blocked；单独处理 BLS Job Openings business error。全部通过后再运行 51 条 verified primary 的 incremental/backfill live audit。
