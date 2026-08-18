# Probe 重试与批准后 Live Audit 结论

## 1. Probe 重试

针对上轮 12 条阻塞映射，使用当前候选的 Adapter、直连官方网络路径重试，并连接远程验收 PostgreSQL：

- 11 条通过并原子晋级 `verified/primary`；
- 1 条仍阻塞：`US.JOB.OPENINGS`，BLS 返回 HTTP/business error；
- Treasury 2Y、10Y、Real 10Y：全部通过；
- Federal Reserve Board 8 条：全部通过；
- SSH 隧道执行后关闭。

远程库当前状态：

- verified mappings：62；
- verified primary：54；
- needs_review：3（其中 active 只有 `US.JOB.OPENINGS`，另外两个是 BEA 派生概念）；
- license_required：4。

## 2. 批准后增量 Live Audit

对当前远程库的 8 个 Provider 执行增量 audit：

| Provider | 状态 | 结果 |
|---|---|---|
| BEA_API | passed | 22 个映射，1,364 条观测 |
| CENSUS_EITS_API | passed | 2 个映射，133 条观测 |
| NYFED_MARKETS_API | passed | 3 个映射，3,740 条观测 |
| BLS_API_V2 | failed | 2025-10-01 有 5 个官方缺值，质量门禁拒绝 |
| EIA_API_V2 | failed | HTTP 403，响应压缩解码失败 |
| FED_BOARD_FILES | failed | 当前 live-audit 默认网络路径 ConnectError；直连 probe 已通过 |
| FRED_API | failed | T5Y5 序列 2021-09-06 后 56 个缺值 |
| US_TREASURY_XML | failed | 当前 live-audit 默认网络路径 ConnectError；直连 probe 已通过 |

完整原始结果：[live-incremental-audit-after-approval.json](./2026-08-18-live-incremental-audit-after-approval.json)。

## 3. 结论

映射审批已经从 14 个旧 verified primary 扩展到 54 个当前 primary。BEA、Census、NY Fed 和映射直连 probe 已闭环；剩余问题属于 BLS 官方缺值、EIA 授权/响应、FRED 数据质量和 live-audit 网络出口，不应通过修改 vintage 或强制发布绕过。

下一步应让服务器 Worker 使用可访问 Federal Reserve/Treasury 的网络执行 live audit，并处理 BLS/EIA/FRED 质量问题；完成前不执行正式 backfill 发布或业务验收。
