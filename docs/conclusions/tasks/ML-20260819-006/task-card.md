# 任务卡：ML-20260819-006

- 来源主线程：MacroLens 项目统筹主线程
- 目标与业务场景：将 TradingView 535 项指标的页面显示名称补齐为中文，同时保留英文原名和 Provider 原始标识。
- 成功标准：
  - 535 项 `name_zh` 均为中文显示名；
  - `name_en` 和 `provider_series_id` 保持原始值不变；
  - 不修改 observation、vintage、Provider 映射和指标树归属；
  - 中文名称生成规则可审计、可重复生成，并有唯一性/覆盖测试；
  - 真实验收页面和 API 明细显示中文名称。
- 范围内：TradingView 注册表生成、中文名称词典/翻译映射、seed、相关测试和 UI 验收。
- 范围外：修改英文 Raw Series 名称、翻译官方 Provider 61 项、修改数据库 Schema、重新采集数据。
- 分配部门席位：宏观研究部、研发部、测试部、集成发布部、运维部（由当前主线程执行）。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-tradingview-full-catalog`，`origin/master@0750c63`。
- 公共接口或 Schema 影响：不改 Schema；API 继续使用已有 `name_zh` / `name_en` 字段。
- 必须执行的检查：翻译覆盖测试、后端全量测试、ruff、mypy、Web lint/test/build、PR CI、Compose seed、真实 UI 验收。
- 阻塞时返回条件：若无法为某个指标确认专业中文口径，保留英文原名并标记待人工审核，不生成看似准确的错误翻译。
