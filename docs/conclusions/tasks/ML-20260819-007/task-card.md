# 任务卡：ML-20260819-007

- 来源主线程：MacroLens 项目统筹主线程
- 目标与业务场景：为 TradingView 美国失业率 `ECONOMICS:USUR` 增加 chart session 历史趋势同步，供现有趋势、历史和统计页面使用。
- 成功标准：
  - WebSocket chart session 可解析 USUR 历史点并完整回补到 `available_data_range_begin_date`；
  - 历史点写入现有 observation_vintage/latest，不保存原始帧，不覆盖旧 vintage；
  - 管理员可从当前指标详情触发“同步历史数据”Job；
  - Job 幂等、失败隔离、权限正确，现有最新值同步不回归；
  - 真实页面显示多期 USUR 趋势、历史记录和统计摘要。
- 范围内：TradingView chart session、backfill 模式、USUR 专用历史接口、详情页按钮、测试、部署和真实验收。
- 范围外：多国家详情页、其余 340 项历史扩展、自动调度、Playwright 生产采集、原始 WebSocket 帧存储、新数据库表。
- 分配部门席位：数据源部、数据平台部、研发部、测试部、运维部、集成发布部（由当前主线程执行）。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-tradingview-full-catalog`，`419a43b`。
- 允许修改的模块：TradingView Provider/同步任务、Admin API、数据浏览器详情组件、测试和部署文档。
- 公共接口或 Schema 影响：新增管理员历史同步 POST 接口；不新增数据库表或迁移。
- 依赖任务：当前服务器 mihomo 出口必须恢复 TradingView TLS/WebSocket 访问；协议测试可先使用脱敏 fixture。
- 必须执行的检查：Provider 单测、后端全量、ruff、mypy、Web lint/test/build、PR CI、Compose seed、真实 USUR 历史同步和趋势 UI 验收。
- 阻塞时返回条件：网络出口未恢复时保留协议/fixture 实现和明确失败证据，不伪造历史观测或发布成功状态。
