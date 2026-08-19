# ML-20260819-001｜TradingView 535 项指标树完整验收

- 来源主线程：当前用户任务主线程
- 目标与业务场景：将 TradingView 经济目录中的 535 个美国宏观指标完整写入指标树，在验收环境页面展示并可按来源筛选。
- 成功标准：Registry 含 535 个唯一指标；CI 全绿；版本合并并打标签；验收库完成 migration/seed 和可获取值导入；UI 显示 535 条及 13 个分类；输出可访问验收链接。
- 范围内：TradingView Registry、Provider 大批量采集完成条件、seed 状态、CI seed 顺序、验收部署、数据导入、浏览器 E2E、结论报告。
- 范围外：自动调度、Playwright 采集、原始 WebSocket 帧保存、商业数据许可证采购、修复服务器到 TradingView 的外部网络出口。
- 分配部门席位：数据源、研发、测试、集成发布、运维、知识管理职责由当前任务线程依次执行。
- 工作树与起始提交：`E:/workerspace/projects/20260709/macrolens-tradingview-full-catalog`，基线 `5870a41`，分支 `codex/tradingview-full-catalog`。
- 允许修改的模块：`backend/src/macrolens_worker/providers/tradingview.py`、TradingView seed/生成脚本、相关测试与文档、验收 CI 顺序。
- 公共接口或 Schema 影响：无数据库 Schema 迁移；不改变公开 API；目录数据从 23 扩展到 535。
- 依赖任务：PR #15 已合并；验收 Compose 项目 `macrolens-acceptance-20260814`；用户已授权 migration、seed、同步和部署。
- 必须执行的检查：根 `AGENTS.md` 六项门禁、PR CI、服务器容器健康/readiness、真实浏览器指标树与表格验收。
- 预期交付物：合并提交与版本标签、535 项验收数据、验收链接、七项结论报告。
- 阻塞时返回条件：仅在权限、目标服务器不可达或不可恢复的外部依赖阻止 UI 展示时返回；单项采集失败应记录为候选并继续。
