# ML-20260819-003｜美联储研究框架指标树重构

- 来源主线程：当前用户任务主线程
- 目标与业务场景：将 MacroLens 当前 TradingView 535 项从 13 个来源栏目重构到七个美联储式研究域，保持数据、状态和筛选能力不变。
- 成功标准：根树固定七个一级研究域；535 个 TradingView 指标各有且仅有一个主研究主题；340 READY 与 195 UNAVAILABLE_US 不变；跨域关系只保存标签；API/UI/真实验收通过。
- 范围内：领域词汇、基础 taxonomy 名称和父子关系、TradingView 确定性分类器、Registry/seed、主题筛选、树 API/UI、测试、部署和结论报告。
- 范围外：修改观测值或 vintage；复制指标叶节点；增加新 Provider；为美国不存在的 Symbol 伪造映射；自动调度和历史回填。
- 分配部门席位：宏观研究、架构、数据平台、研发、测试、集成发布、运维和知识管理职责由当前任务线程依次执行。
- 工作树与起始提交：`E:/workerspace/projects/20260709/macrolens-tradingview-full-catalog`，基线 `4f09927`，分支 `codex/fed-research-taxonomy`。
- 允许修改的模块：领域词汇、taxonomy/TradingView Registry 与生成器、seed、目录投影校验、树组件和对应测试/文档。
- 公共接口或 Schema 影响：不修改数据库 Schema；保留 `macro-default` API 路径，节点结构和主题 facet 内容发生兼容性可见变化。
- 依赖任务：PR #19 已合并；当前验收环境为 `v2026.08.19-tradingview-full-catalog.3`；用户已授权实现该方案。
- 必须执行的检查：Registry 唯一归属与计数测试、taxonomy API 层级测试、UI 七域展开测试、根 `AGENTS.md` 六项门禁、PR 四项 CI、服务器 migration/seed、readiness、数据库投影和浏览器 E2E。
- 预期交付物：七域研究树、535 项主归属与跨域标签、合并提交和版本标签、验收链接、七项结论报告。
- 阻塞时返回条件：只有某指标无法由确定性规则唯一归属或现有 API 无法表达唯一主归属时返回；不得使用运行时 AI 模糊分类直接写生产。
