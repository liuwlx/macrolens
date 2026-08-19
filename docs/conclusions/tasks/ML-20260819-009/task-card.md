# 任务卡：ML-20260819-009

- 来源主线程：MacroLens 项目统筹主线程
- 目标与业务场景：修复用户浏览器持续加载旧数据页前端包，导致指标树点击无反应的问题。
- 根因证据：验收 `/data` 返回 `Cache-Control: s-maxage=31536000`、`x-nextjs-cache: HIT`，页面 HTML 可被缓存一年。
- 成功标准：
  - `/data` 必须动态渲染并返回 no-store/no-cache；
  - 浏览器刷新后加载最新构建，不依赖手工清缓存；
  - 分类与叶指标点击在真实用户浏览器路径中更新右侧表格和详情。
- 范围内：Next.js 数据页动态策略、Cache-Control 响应头、回归测试、部署和真实 UI 验收。
- 范围外：Provider 映射、数据库、指标中文名和同步数据。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-tradingview-full-catalog`，`edbb640`。
- 必须执行的检查：Cache-Control 测试、Web lint/test/build、PR CI、部署后 curl 响应头、真实 UI 点击验收。
