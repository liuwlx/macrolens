# TradingView 手动同步 V1 实现结论

## 1. 问题与场景

用户要求按 N0—N11 工程实现文档落地 TradingView 第一版：页面手动同步、直接 WebSocket、23项美国经济指标、唯一 PostgreSQL、页面刷新；明确不使用自动调度、浏览器采集、原始采集包或额外数据库。

## 2. 分析过程

- 在独立 worktree `E:\workerspace\projects\20260709\macrolens-tradingview-v1` 中基于刷新后的 `origin/master@b634c95` 开发。
- 复用现有 `ProviderAdapter`、Job claim/heartbeat、同步发布、SourceSeries、Taxonomy和数据浏览器能力。
- 发现直接 WebSocket 会对同一 Symbol 返回多次 `qsd` 增量字段，必须合并消息，否则后续只含 `reference-last-period-start` 的消息会覆盖最新值。
- 发现项目现有目录校验只允许旧的61项目录，因此增加 `US.TV.*` 和 `tv-*` 的受控扩展校验，而不破坏旧目录。
- 发现单个TradingView Symbol失败不能触发全Provider失败，因此在同步质量处理中将缺失Symbol降为逐项警告，成功项继续发布。

## 3. 解决流程

1. 先写 WebSocket Codec、期间解析和 Adapter 测试。
2. 实现 TradingView 直接连接、批量订阅、qsd合并和标准化观测。
3. 将 Provider 注册到 Worker 和 Seed。
4. 增加23项TradingView Registry和指标树扩展。
5. 让同步链路支持 `persist_raw=False`，不保存TradingView原始包。
6. 增加手动同步API、Job详情API和前端按钮/轮询/刷新。
7. 更新OpenAPI、收集模块审查清单和Live audit Provider清单。
8. 运行后端全量检查、前端lint/build和真实TradingView 23项Smoke。
9. 创建本地提交 `4f5d55da3bb324e3bc17a584cdd1def04f7874f2`。

## 4. Agents、skills、tools 与文档

- Agents：主 Codex Agent；未使用子 Agent。
- Skill：`tdd`，用于按红测、实现、回归的垂直切片推进。
- Tools：PowerShell、`rg`、Git worktree、Git、Python 3.12、pytest、Ruff、Mypy、npm、Node、`apply_patch`。
- 已读规则：`AGENTS.md`、组织配置、组织运行手册、开发链路宪法索引、01本地开发与冻结宪法。
- 已读资料：TradingView接口分析、系统架构、Worker功能地图、N0—N11工程文档。

## 5. 实现结果

已实现：

- `TRADINGVIEW_WEB` Provider；
- WebSocket动态URL、Origin、User-Agent和Session；
- `~m~length~m~JSON`拆包、粘包、心跳和消息分流；
- `qsd`增量字段合并；
- 日/周/月/季/年期间解析；
- 23项TradingView Registry和指标树扩展；
- 不保存TradingView Raw Object；
- 管理员手动同步接口：`POST /api/v1/admin/providers/{provider_code}/sync`；
- Job详情接口：`GET /api/v1/admin/jobs/{job_id}`；
- 页面“数据同步”按钮和状态轮询；
- 失败Symbol隔离和部分成功结果；
- OpenAPI、Provider审查清单和测试。

## 6. 验证结果

通过：

- Python 3.12 后端全量测试：278 passed；
- `ruff check backend`：通过；
- `mypy backend/src`：72个源文件通过；
- Web lint：通过，保留2个既有warning；
- Web build：通过；
- 真实TradingView批量Smoke：23 requested，23 observations返回；
- `git diff --check`：通过；
- worktree提交后干净。

未完成：

- 未执行远程PostgreSQL migration/seed，因为当前没有获得本轮远程数据库写入授权；
- 未启动服务器Compose、未部署、未生成验收链接；
- Web Vitest受到当前依赖环境的 `@csstools/css-calc` CommonJS/ESM加载错误影响，未能运行测试用例；该错误发生在测试环境初始化阶段，尚未进入业务测试。

## 7. 值得沉淀的经验

- TradingView同一Symbol的多个qsd消息是增量字段，Parser必须合并，不得用最后一条消息覆盖完整快照。
- 目录扩展应有明确前缀和受控校验，避免破坏旧目录的完整性门禁。
- UI只需要一个按钮，但长任务仍应通过现有Job/Worker执行，不能让FastAPI请求阻塞等待WebSocket。
- 不保存原始包时，必须保留SourceSeries、IngestionRun、Vintage和Latest血缘，并在文档中明确无法离线重放的代价。
- 真实Provider Smoke应在单元测试后执行，23项批量Smoke比只测单Symbol更早暴露协议增量字段问题。

## 8. 更好的初始提示词

> 在独立worktree基于最新origin/master实现TradingView手动同步V1：页面管理员按钮触发一个后台Job，Worker直接连接TradingView WebSocket，批量同步23项最新值，按Symbol隔离失败，写入唯一PostgreSQL并刷新页面。不要自动调度、浏览器采集、Raw Object、历史回填或新中间件。先写Codec/Adapter/API/UI测试，再实现，通过后端全量测试、Web lint/build和真实23项WebSocket Smoke。

## 9. 当前场景一次解决的更优方案提示词

> 先读取N0—N11工程文档、现有Provider/Job/Seed/DataBrowser代码和TradingView实测协议。创建独立分支和worktree，按垂直切片完成：Codec与qsd合并 → USUR真实Smoke → 23项Adapter → Registry/Seed → Vintage/Latest发布 → 管理员同步API → 页面按钮轮询刷新。每一步先写行为测试；禁止改主工作区、禁止远程部署或Seed，除非有明确授权。最终报告提交SHA、测试结果、真实Provider结果和未完成的远程验收步骤。
