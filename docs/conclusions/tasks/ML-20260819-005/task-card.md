# 任务卡：ML-20260819-005

- 来源主线程：MacroLens 项目统筹主线程
- 目标与业务场景：修复真实验收发现的前端错误文案匹配遗漏。
- 成功标准：Worker 返回 `TradingView WebSocket TLS connection failed` 时，数据浏览器显示中文代理/出口诊断，不显示 `ProviderDataError:` 或空的 `ConnectionResetError:`。
- 范围内：`apps/web/lib/sync-errors.ts` 及其回归测试。
- 范围外：TradingView 连接协议、数据库、指标树和同步任务状态机。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-tradingview-full-catalog`，`origin/master@0a18517`。
- 必须执行的检查：错误文案测试、Web lint、Web build、PR CI 和真实页面点击验收。
- 依赖任务：ML-20260819-004 已发布，但真实 UI 验收发现 TLS 文案中包含 `TLS` 后未被前端匹配。
- 阻塞时返回条件：保留真实 UI 快照和失败 Job，不能修改服务器容器内代码。
