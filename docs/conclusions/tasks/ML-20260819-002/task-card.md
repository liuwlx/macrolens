# ML-20260819-002｜处理 TradingView 剩余 195 个美国不可用指标

- 来源主线程：当前用户任务主线程
- 目标与业务场景：继续处理 535 项目录中尚无数据的 195 项，确认是否可修复映射；可修复项同步数据，不可修复项给出准确且有证据的美国不可用状态。
- 成功标准：195 项逐项获得确定诊断；不把 `no_such_symbol` 误标为待审批映射；UI 可区分“美国无此序列”与“待映射”；535 项目录和 340 项已验证映射不回退；完整门禁、CI、部署和 UI 验收通过。
- 范围内：TradingView Symbol 状态探测、Registry 状态、seed 映射状态、数据浏览器 availability 契约、Web 标签与测试、结论报告。
- 范围外：为不存在的美国符号伪造值；改用其他国家数据；模糊别名替换；自动调度；历史回填；采购 TradingView 商业 Feed。
- 分配部门席位：数据源、数据平台、研发、测试、集成发布、运维与知识管理职责由当前任务线程依次执行。
- 工作树与起始提交：`E:/workerspace/projects/20260709/macrolens-tradingview-full-catalog`，基线 `bec550d`，分支 `codex/tradingview-remaining-195`。
- 允许修改的模块：TradingView Registry/生成脚本、seed、数据浏览器后端与前端 availability 契约、对应测试和文档。
- 公共接口或 Schema 影响：预计扩展 SeriesAvailability 枚举；不修改数据库 Schema。
- 依赖任务：PR #16/#17/#18 已合并；验收 Compose `macrolens-acceptance-20260814` 当前健康；用户已授权继续处理和部署验收。
- 必须执行的检查：195 项真实 WebSocket 状态复核；根 `AGENTS.md` 六项门禁；PR 四项 CI；服务器 migration/seed、readiness、数据库计数和真实 UI E2E。
- 预期交付物：195 项诊断与 Registry 状态、准确 UI 标签、合并提交/标签、验收链接、七项结论报告。
- 阻塞时返回条件：只有发现需要登录、付费授权或无法由公开 TradingView 协议确认的符号时才返回；`no_such_symbol` 应作为确定的美国不可用结果收口。
