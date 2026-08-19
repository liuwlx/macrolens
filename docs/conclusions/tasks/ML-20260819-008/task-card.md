# 任务卡：ML-20260819-008

- 来源主线程：MacroLens 项目统筹主线程
- 目标与业务场景：修复指标树点击分类后右侧明细仍显示上一个指标的问题。
- 根因：`onNode` 只更新 `node`，没有清空旧的 `q` 和 `series`；右侧 `/series/browser` 继续使用上一个指标的精确搜索条件。
- 成功标准：
  - 点击任意指标树分类后，右侧表格按新分类刷新；
  - 旧指标不再锁定右侧查询；
  - 点击叶指标仍能精确选中并刷新详情；
  - URL 状态、分页和筛选保持可复现。
- 范围内：浏览器 URL 状态选择逻辑、指标树入口、回归测试、部署和真实 UI 验收。
- 范围外：Provider 映射、中文名称、数据库、同步任务和历史数据。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-tradingview-full-catalog`，`1fb84dc`。
- 必须执行的检查：browser-query 测试、Web lint/build、PR CI、Compose 部署和真实分类/叶指标点击验收。
- 结论：分类选择必须同时清空旧 `q` 和 `series`，由新分类查询完成后自动选中首个指标。
