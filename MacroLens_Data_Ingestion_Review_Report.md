# MacroLens v1.0.2 数据采集模块复核报告

生成时间：2026-08-02T05:36:47Z

## 结论

本次逐一复核了 8 个时间序列 Adapter、BLS 发布日历、FOMC 官方材料采集、文档采集，以及统一的修订与发布流水线。

**能够作出的工程保证是：所有启用映射都采用失败关闭（fail closed）策略。** 返回不完整、身份不一致、分页缺页、重复冲突、历史起点漂移、最新期过期或质量门禁失败时，整批数据进入 `quarantined`，不会把“半盘菜”端给前端。

不能作出的虚假保证是“61 条指标现在都能采集”。注册表共有 **61** 条指标，其中：

- **31 条**映射已启用并通过结构、代码和 Mock HTTP 契约复核；
- **30 条**仍被明确禁用：24 条 BEA 精确元数据映射、2 条 Census 维度映射、4 条授权或法务限制数据；
- 当前环境没有外网 DNS、官方 API Key 和 PostgreSQL，故未在此沙箱执行真实官方全历史回填。

换句话说：已启用的，缺一页都不发布；没核准的，宁可空着，也不拿猜的序列号顶上。

## 覆盖范围

| 模块 | 已启用 | 复核结果 | 关键边界 |
|---|---:|---|---|
| FRED / ALFRED | 12 | 当前、回填、历史 vintage；分页/计数/起点/重复检查 | 必须定期跑全历史及 vintage 审计 |
| BLS API v2 | 12 | 50 序列分批、20 年窗口、全序列覆盖检查 | 无法重建从未抓取过的历史初值 |
| NY Fed Markets | 3 | 年度窗口、字段/聚合/重复检查 | 历史修订以平台抓取快照为准 |
| Treasury XML | 3 | 曲线/期限字段固定、逐年拉取、空窗拦截 | 官方 feed 不提供完整修订账本 |
| EIA API v2 | 1 | 5,000 行分页、total 对账、seriesid 路由 | 新数据集需另行固定 route/facet |
| BEA API | 0 | Adapter 已加严格身份检查 | 24 条精确 SeriesCode/LineNumber 未批准，保持禁用 |
| Census EITS | 0 | Adapter 已加严格维度和重复检查 | 2 条维度组合未批准，保持禁用 |
| DOL Open Data | 0 | 通用 JSON/CSV 分页 Adapter 已复核 | 初请当前使用 FRED ICSA；DOL 路由未启用 |
| BLS 发布日历 | 5 类 | iCalendar 解析、UID/日期/空结果门禁 | 只覆盖当前产品所需 5 类 BLS 发布 |
| FOMC | 日历+材料 | 部分解析即失败；材料发现后必须全部入队 | SEP、点阵图、投票等结构化字段尚未实现 |
| 文档采集 | 官方白名单 URL | SSRF、重定向、大小、页数、版本、哈希门禁 | 不是全网爬虫，完整性取决于官方 URL 清单 |

## 关键修复与强化

1. **修订语义**：每个唯一 vintage 只追加；旧 vintage 和相同数值 vintage 也保留；只有更晚 vintage 可以更新 serving row；同一 vintage 不同值直接阻断。
2. **FRED/ALFRED**：核验官方 metadata 起始期；当前观察值与 vintage dates 都完整分页；重复页、总数漂移或缺页即失败。
3. **BLS**：按官方 20 年窗口和 50 序列批次请求；要求每个请求的 Series ID 都返回；Series ID 和有限 catalog 元数据固定。
4. **EIA**：按 5,000 行上限分页并与 `total` 对账；支持 `seriesid` 路由；重复期间和历史起点错误被阻断。
5. **NY Fed**：按年度窗口抓取；EFFR/SOFR/RRP 的 route、字段、过滤条件和聚合规则固定；RRP 可允许历史稀疏窗口但不允许重复冲突。
6. **Treasury**：名义与实际曲线 feed、期限字段和首日固定；逐年请求，异常空窗失败关闭。
7. **BEA/Census**：不再模糊命中后直接发布；BEA 同一身份出现冲突描述会失败，Census 维度未固定或同期间重复会失败。
8. **FOMC/日历**：只解析一部分会议或缺少发现到的材料时拒绝提交；BLS 日历重复 UID、无可识别事件时失败。
9. **定期审计**：新增不发布数据的官方 live audit 工作流；周度增量、月度全历史，FRED vintage 回填保留手工高成本门禁。

## 自动化验证

- Python 测试：**86 passed**；
- Python 覆盖率：**56.96%**；
- Provider/采集专项 Mock HTTP 契约：覆盖分页、缺页、重复、边界、身份冲突、稀疏窗口和部分解析失败；
- Python compileall：通过；
- API 真实进程 smoke：`/live` 200、`/health` 200、无数据库时 `/ready` 正确返回 503、`/openapi.json` 62 paths、`/metrics/` 200；
- OpenAPI：62 paths，生成一致性检查通过；
- 数据源结构审计：61 条；31 条启用且全部 ready；30 条禁用；
- Alembic offline upgrade：864 行，成功生成；
- 当前沙箱未执行：真实官方 API 全历史回填、PostgreSQL 实库发布、Docker Compose 和浏览器端全栈测试。

## 上线门禁

生产环境只有同时满足以下条件，才可以把“采集完整”写进发布说明：

1. `DATA_INGESTION_READINESS.json` 中 `enabled_blocked_count = 0`；
2. 周度 `incremental` live audit 对 FRED、BLS、NY Fed、Treasury、EIA 全部通过；
3. 月度 `backfill` live audit 全部通过；
4. 需要 point-in-time 回测时，FRED `vintage_backfill` 通过；
5. 24 条 BEA 和 2 条 Census 映射完成官方身份/维度签字后才能启用；
6. 4 条授权数据必须先录入 `license_policy`；
7. FOMC 页面中的 SEP、点阵图、投票结果在结构化采集器完成前不得标注为完整实时数据。

## 运行命令

```bash
# 静态注册表/映射审计
PYTHONPATH=backend/src python -m macrolens_worker.main audit-data --structural \
  --output DATA_INGESTION_READINESS.json

# 官方 API，不写生产表、不发布
PYTHONPATH=backend/src python -m macrolens_worker.main audit-live \
  --mode incremental \
  --provider FRED_API --provider BLS_API_V2 \
  --provider BEA_API --provider CENSUS_EITS_API --provider DOL_OPEN_DATA_API \
  --provider NYFED_MARKETS_API --provider US_TREASURY_XML \
  --provider EIA_API_V2 \
  --output LIVE_INGESTION_AUDIT.json

# 月度完整历史审计
PYTHONPATH=backend/src python -m macrolens_worker.main audit-live \
  --mode backfill \
  --provider FRED_API --provider BLS_API_V2 \
  --provider BEA_API --provider CENSUS_EITS_API --provider DOL_OPEN_DATA_API \
  --provider NYFED_MARKETS_API --provider US_TREASURY_XML \
  --provider EIA_API_V2 \
  --output FULL_HISTORY_AUDIT.json
```

机器可读详情见 `DATA_COLLECTION_MODULE_REVIEW.json`；结构化就绪状态见 `DATA_INGESTION_READINESS.json`。
