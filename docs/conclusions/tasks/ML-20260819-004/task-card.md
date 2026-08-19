# 任务卡：ML-20260819-004

- 来源主线程：MacroLens 项目统筹主线程
- 目标与业务场景：修复数据浏览器点击“数据同步”后出现 `ConnectionResetError` 的用户可见错误。
- 成功标准：
  - 能在验收环境复现或通过日志证明该异常的真实边界；
  - 同步任务失败时 API 返回稳定的 RFC 9457 problem details，页面显示可理解的错误信息；
  - 网络连接被远端重置时，Worker 具备有限、可观测、不会重复写入的重试/失败行为；
  - 正常同步路径和已有 340 项数据不受破坏。
- 范围内：数据浏览器同步按钮、TradingView 同步 API/Worker 网络错误处理、回归测试、部署验收。
- 范围外：重新设计 TradingView 采集协议、修改指标树、改变 observation vintage 规则。
- 分配部门席位：研发部、测试部、运维部（由当前主线程直接执行）。
- 工作树与起始提交：`E:\workerspace\projects\20260709\macrolens-tradingview-full-catalog`，`47d3d4f`。
- 允许修改的模块：`apps/web/components/data-browser`、`backend/src/macrolens_api`、`backend/src/macrolens_worker`、对应测试和结论报告。
- 公共接口或 Schema 影响：优先不改 Schema；若修改 API 错误响应，必须补 OpenAPI/契约测试。
- 依赖任务：TradingView 指标树发布 `7d45365` 已部署。
- 必须执行的检查：针对性后端测试、前端测试/lint/build、完整门禁、远程 Compose 健康检查、真实 UI 点击验收。
- 预期交付物：修复提交、测试证据、远程验收结果、`docs/conclusions` 结论报告。
- 阻塞时返回条件：若远程网络持续阻断，保留脱敏日志，明确区分代码问题与外部网络问题，不在服务器容器内改代码。
