# Demo 深层分类与详情加载修复工作报告

任务 ID：`ML-20260804-004`

## 1. 问题与场景

数据概览页原先把 `has_children` 当成分类节点可展开的唯一条件，导致“没有子分类、但自身直接挂载指标”的叶分类无法展开，医院服务等真实叶节点因此看不到指标。深层 taxonomy 搜索还可能丢失祖先路径，Live 空数据也没有区分“从未入库”和“指定时点尚不可用”。同时，本地验收缺少一套确定、可重复的 Demo 数据：页面无法稳定覆盖深树、详情、修订、分析和导出；若简单绕过数据库，又会破坏真实认证与工作区边界，甚至在只读模式中补写缺失工作区。

本次修复交付了只读 Demo 数据面和对应 Web 交互：61 个 canonical 指标具有稳定 ID、固定时间锚点和确定性数值；深层分类、叶节点指标、详情和只读分析可完整加载；Demo 写操作由前端提示和服务端 `409 demo_read_only` 双重阻断。Demo 指标读取不访问业务指标表，但认证用户和现有工作区仍从真实数据库读取；用户没有工作区时直接返回 409，绝不自动创建。Live 模式继续使用真实数据，并携带明确的 availability 语义。

## 2. 分析过程

排查先沿 Web 的树节点、明细表、详情面板和公共 TypeScript 契约追踪请求链，确认叶分类的点击、caret、键盘 ArrowRight 和 `aria-expanded` 分别重复判断了 `has_children`。因此把可展开性收敛为一个派生规则：`has_children || direct_series_count > 0`。同时检查 URL 固定快照逻辑，发现 `not_ingested` 也会误写 `data_as_of`，于是把“可固定快照”限定为确有 current observation 的 `available` 指标。

后端分析把“Demo 业务数据零读取”和“真实身份认证”拆成两个边界。分类与指标 GET 使用确定性 Demo provider，不构造业务读取 session；认证 cookie、CurrentUser 和 CurrentWorkspace 仍走真实数据库。架构 P1 复核进一步发现两个风险：taxonomy 的五类过滤与逐层祖先保留不完整，以及只读 Demo 在工作区缺失时仍可能触发 ORM 创建。前者通过逐层只返回直系子节点、按后代节点或指标匹配保留祖先并重算计数解决；后者把 data mode 分流提前到任何 `add`、`commit`、`refresh` 或 ORM 对象构造之前。

零写结论没有仅依赖代码审查。验收前后对 13 张业务表计算状态哈希，结果逐表一致；focused 测试也证明 Demo 的 `add`、`commit`、`refresh` 调用均为 0，而 Live 对应创建路径仍各调用 1 次。这样既验证 Demo 不写数据，也避免把只读错误实现成 Live 功能退化。

## 3. 解决工作流与验收结果

1. Engineering-01 用 TDD 修复叶分类展开、`not_ingested` 空态、Demo banner/只读能力、CSV 标记和深层搜索祖先路径，并补齐组件与 Playwright 用例。
2. Engineering-02 用 TDD 增加 `MACROLENS_DATA_MODE`、61 指标确定性数据、深层 taxonomy 注册表、详情/修订/分析/CSV、Live availability 和 `409 demo_read_only`。
3. Architecture 复核发现并推动修复真实认证边界、taxonomy 过滤/层级、固定频率点数以及 Demo 缺失工作区零写四类 P1；最终架构结论为 PASS。
4. Integration & Release 按 Web、后端、P1、零写 P1 的顺序 cherry-pick，处理构建副作用，复跑 focused 门禁、OpenAPI、remote-dev static、Web typecheck/build 和 commit-range diff-check。
5. 运行验收在 `mode=demo`、状态 `ready` 的完整栈上执行页面、API、CSV、写阻断、数据库哈希和多视口检查。

真实门禁与运行证据如下：

| 检查 | 结果 |
|---|---|
| 后端全量测试 | PASS：132 项 |
| Web 全量 Vitest | PASS：21 项 |
| Playwright | PASS：9 项 |
| Web production build | PASS：15 个路由生成 |
| 架构复核 | PASS |
| 运行状态 | `mode=demo`，`ready` |
| taxonomy | 61 个指标；PCE 路径深度 8；医院服务叶分类可展开；就业分支 7 个叶分类可达 |
| 指标详情 | 观察值 120、修订 24、分析点 120 |
| CSV 与写阻断 | CSV 明确标记 `data_mode=demo`；业务 mutation 返回 409 `demo_read_only` |
| 零写审计 | 13 张业务表验收前后哈希一致 |
| 浏览器质量 | 五档视口均无根页面横向溢出；`treeErrors=0`；console errors 为 0 |
| Git | 集成提交和完整任务 commit-range `diff --check` 通过，无冲突标记 |

边界披露：全仓 `ruff check backend` 仍有 414 项、`mypy backend/src` 仍有 37 项，均为本任务继承的基线债务，不能记为 PASS；本任务变更范围的 Ruff 与新增 Demo 模块聚焦 mypy 已通过。OpenAPI 在任务生成环境 FastAPI 0.116.1 下为 current（68 paths），主工作区未锁定的 FastAPI 0.141.1 会产生框架级快照漂移；这不是本次业务契约回归，但属于需要后续锁定依赖的可复现性风险。Security 外部 scan 未启动，因此没有安全扫描 PASS 结论，也不得用架构或功能验收替代。

## 4. Agents、skills、tools 与文档

- Agents：来源主线程 `/root` 负责统筹和最终运行验收；Engineering-01 实现 Web；Engineering-02 实现后端、Demo 数据和 remote-dev；Architecture 执行契约与 P1 复核；质量/运行验收席位执行测试、浏览器与零写审计；Integration & Release-01 负责按序集成、回归和本报告。各研发席位未创建子 Agent，本报告任务也未创建子 Agent。
- Skills：Engineering-01 与 Engineering-02 使用 `tdd`，按 RED→GREEN→回归实现可观察的组件、HTTP 和 CLI 契约；Integration & Release 的 cherry-pick、核验和报告没有额外调用 skill。
- Tools：使用 `rg` 与 PowerShell 检索，`apply_patch` 编辑，Git 审查/cherry-pick/diff-check，Python 3.12、pytest、Ruff、mypy 和 OpenAPI 生成器验证后端，Node 22、Vitest、TypeScript、Next build 与 Playwright 验证 Web，并使用浏览器断言、CSV 检查和业务表哈希完成运行验收；协作消息用于任务卡、P1 和候选 SHA 交接。
- 文档与契约：完整阅读根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`docs/architecture.md`、两份 `docs/conclusions/tasks/ML-20260804-004/department-engineering-*.md`，并核对 `macrolens_openapi.yaml`、`database/seed/taxonomy_registry.json`、Web 公共类型和相关测试。报告未记录任何凭据、令牌、连接串或数据库秘密。

## 5. 值得沉淀的经验与模式

- 树节点“可展开”是领域派生值，应统一驱动鼠标、caret、键盘和 ARIA，不能让四条交互路径各自判断。
- Demo 数据与 Demo 身份不是一回事。业务指标可以确定性替代，但认证和工作区所有权仍必须保留真实边界。
- “允许读取真实身份表”不等于“允许补写缺失身份数据”。只读分流必须发生在 ORM 对象构造和任何 session mutation 之前。
- 深树搜索不能只返回匹配节点；应逐层保留祖先、每次只返回直系子节点，并在过滤后重新计算 direct/descendant counts。
- 只读模式需要纵深防护：前端解释与禁用改善体验，服务端 409 提供最终保证，数据库前后哈希证明没有旁路写入。
- 依赖范围约束不足以保证 OpenAPI 快照可复现。生成契约的 FastAPI/Pydantic 版本应锁定，并在固定环境中校验。
- 门禁报告必须区分本次回归、继承债务和未执行检查；“未启动 security scan”不能写成安全通过。

## 6. 更好的初始提示词

> 请修复 MacroLens 数据概览页中深层分类和叶分类无法完整展开、指标详情无法稳定验收的问题，并增加一个默认用于本地验收的只读 Demo 模式。先确认没有子分类但直接挂载指标的叶节点也能通过鼠标和键盘展开，搜索结果逐层保留祖先路径；再用仓库全部 61 个指标生成跨进程一致的深层分类、观察值、修订、分析和 CSV。Demo 的指标读取不能访问业务指标表，但登录用户和现有工作区仍必须真实认证；若用户没有工作区，返回 `409 demo_read_only`，绝不自动创建或执行任何数据库写入。Live 模式保持原写路径，并区分 available、not_ingested、not_available_as_of。请先写失败测试，再实现前后端与 remote-dev 契约；验收必须包含后端/Web 全量测试、9 项 Playwright、production build、架构复核、61 指标、8 层 PCE、医院与就业叶节点、详情/修订/分析/CSV、mutation 409、13 张业务表前后哈希、多视口无根横向溢出和零控制台错误。明确区分历史 Ruff/mypy 债务、OpenAPI 依赖版本漂移和未执行的外部安全扫描，不要输出任何凭据或数据库秘密。

## 7. 更优方案反思与提示词

当前方案在路由边界选择 Demo facade，改动范围可控并已通过验收；更优的长期方案是把分类、指标、详情、修订、分析和导出统一抽象为只读 `QueryStore`，分别由 `SqlReadStore` 与 `DeterministicDemoStore` 实现。认证/工作区依赖保持独立，mutation 完全不进入 QueryStore。这样路由无需反复判断 data mode，availability、许可、CSV 元数据和错误语义可由共享应用服务组装；零写还可由一个统一的只读 session guard 和数据库审计门禁覆盖。与此同时，应锁定 OpenAPI 生成环境并把 13 表哈希、深树浏览器断言和外部安全扫描接入发布门禁。

> 请在不改变现有 HTTP 响应语义的前提下，把 MacroLens 的 taxonomy、series、observations、revisions、analytics 和 export 读取迁移到统一 `QueryStore` 接口，提供 SQL 与确定性 Demo 两个适配器；认证用户和工作区查询保持独立真实依赖，所有 mutation 保持独立命令路径。先用现有 132 个后端测试、21 个 Web 测试、9 个 Playwright 和运行验收锁定行为，再逐路由迁移。Demo adapter 不得获得写 session，缺失工作区必须在构造 ORM 对象前返回 `409 demo_read_only`；SQL adapter 批量计算 availability，避免 N+1。锁定 FastAPI/Pydantic/OpenAPI 生成版本，并在 CI 中执行架构检查、13 张业务表前后哈希、五档无根横向溢出、console/tree error、Ruff/mypy 新增错误基线和外部 security scan。全部通过后才生成发布候选报告，报告不得包含凭据、令牌、连接串或数据库秘密。
