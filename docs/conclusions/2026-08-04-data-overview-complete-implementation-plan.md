# MacroLens 数据概览页完整实现计划

## 1. 问题与场景

当前 `/data` 页面由一个大型客户端组件承担搜索、列表、选中指标、趋势图、历史表格、详情、许可证、修订和导出。它与已确认的目标存在五类差距：

1. 页面结构不是“指标树 + 明细数据表 + 指标详情 + 跨列分析区”。
2. 现有 `/series` 只提供基础检索，不能一次返回表格所需的当前值、上期、变动、环比/季比、同比、筛选计数和稳定分页。
3. 现有 `search_series` 对每条指标分别读取许可证和最新值，存在 N+1 查询风险，无法支撑约 10,000 个指标的浏览场景。
4. 贡献分析、统计摘要、下次发布、AI 能力状态和一致快照导出没有完整契约。
5. URL 状态、响应式抽屉、键盘操作、错误隔离、视觉回归和灰度切换尚未形成可验收闭环。

本计划只定义实现，不修改业务代码。正式实施时必须继续遵守 observation vintage 不可覆盖、许可策略全链路生效、AI 上下文保留 `data_as_of` 和来源引用等项目规则。

## 2. 分析过程

### 2.1 已检查的上下文

- 结构基准：用户确认的中文 UI 字符图，桌面端标注为 `≥1280px`。
- 视觉基准：最初提供的 1536×1024 数据浏览器参考图。
- 页面入口：`apps/web/app/(app)/data/page.tsx`。
- 全站外壳：`apps/web/components/app-shell.tsx`。
- 图表组件：`apps/web/components/chart.tsx`。
- 前端 API 与类型：`apps/web/lib/api.ts`、`apps/web/lib/types.ts`。
- 后端接口：`backend/src/macrolens_api/routers/series.py`、`taxonomies.py`、`workspace.py`、`releases.py`、`documents.py`、`ai.py`。
- 后端服务和模型：`backend/src/macrolens_api/services/series.py`、`models.py`、`schemas/models.py`。
- 联动页面：`apps/web/app/(app)/compare/page.tsx`、`ai/page.tsx`。
- SDK：`packages/sdk-typescript/src/index.ts`。
- 自动化：`backend/tests`、`apps/web/components/ui.test.tsx`、`apps/web/e2e/critical-path.spec.ts`、Playwright 配置。

### 2.2 简要诊断

这不是单纯的 UI 改版。页面首屏表格需要跨多个数据域聚合，筛选、树节点、表格选中项、详情、趋势和分析还必须共享同一快照与 URL 状态。如果直接在现有 `page.tsx` 上追加组件，会继续扩大客户端请求瀑布、查询 N+1、许可判断分散和状态不一致问题。正确边界是先提供面向数据浏览器的聚合读接口，再把页面拆成独立可失败、可缓存、可测试的区域。

### 2.3 来源优先级

发生冲突时按以下顺序决策：

1. 中文字符图决定页面信息架构、区域位置和桌面端 `≥1280px` 三列关系。
2. 1536×1024 参考图决定视觉密度、间距、卡片、表格行高和信息层级。
3. 现有 MacroLens AppShell、设计变量、按钮、表格和图表组件决定品牌一致性。
4. 本计划中的工程规则决定数据、安全、性能和降级行为。

## 3. 解决流程与完整实现计划

### 3.1 Key changes

| Change | Why | Impact |
|---|---|---|
| 新增数据浏览器聚合 API，不再由页面拼接几十次请求 | 当前接口无法稳定提供表格汇总，且存在 N+1 | 首屏数据一次返回，口径统一，便于性能与许可审计 |
| 将 `/data` 拆成页面控制器、筛选栏、懒加载指标树、表格、详情和分析区 | 当前单文件同时承担状态、网络和渲染 | 每个区域可独立加载、失败、测试和优化 |
| 以 URL 为可分享状态源，以 React Query 为服务端状态源 | 当前只同步 `q` 和 `series`，刷新后大量状态丢失 | 筛选、排序、分页、选中项、标签和时间范围可复现 |
| 把 `data_as_of`、许可能力和不可用原因加入所有关键响应 | 表格、图表、贡献、导出和 AI 不能使用不同快照或绕过许可 | 防止静默回落到最新值、数据泄漏和解释不一致 |
| 固定桌面三列与跨列分析区，同时定义窄屏抽屉/底部面板 | 字符图已经确认结构，但当前实现没有响应式状态模型 | 1280px 以上忠实还原，窄屏不挤压核心表格 |
| 加入 feature flag、视觉回归和明确回滚阈值 | 改动覆盖 API、状态和主研究页面，风险高 | 可以管理员预览、灰度验证并在异常时快速切回旧版 |

### 3.2 推荐模型设置

- 实施代理：GPT-5.6，`reasoning_effort=high`。原因是任务同时涉及 SQL 聚合、时间序列口径、许可证、安全、跨页面状态和视觉还原。
- 复核代理：GPT-5.6，`reasoning_effort=high`，与实施上下文隔离，重点检查查询口径、授权泄漏、响应式和视觉差异。
- 输出详细度：`text.verbosity=medium`；代码与测试结果精确，过程说明保持紧凑。
- 不建议全局使用 `max`；只有贡献分解或复杂 SQL 在代表性测试中仍出现错误时再局部提高。

### 3.3 用户可见目标

完成后，研究员进入 `/data` 应能：

1. 在保留 MacroLens 顶部导航和全站侧边导航的前提下浏览指标树。
2. 通过来源、主题、频率、单位、季调和发布日期筛选明细表。
3. 在同一张表中看到当前值、上期值、绝对变动、频率对应的期间变化和同比。
4. 单击表格行后立即查看指标详情、趋势、贡献/不可用说明、统计摘要、历史、修订和相关文档。
5. 收藏指标、加入对比、导出允许下载的数据并将指标带入 AI 上下文。
6. 刷新、复制 URL 或前进后退时恢复同一浏览状态。
7. 在桌面、平板和手机上完成核心浏览操作，并能使用键盘和屏幕阅读器。

### 3.4 范围与非范围

范围内：

- `/data` 页面重构及其专用 API、Schema、SDK 和测试。
- `/compare` 接收预选指标参数。
- `/ai` 接收指标上下文并显示能力禁用原因。
- 收藏、文档、修订、发布日历的现有接口联动。
- 新版预览开关、运行指标、视觉验收和回滚。

范围外：

- 不改变现有 AppShell 的信息架构和品牌。
- 不重建或覆写 observation vintage。
- 不执行任意 `weight_expression`，不引入通用公式解释器。
- 不重做 `/compare`、`/ai`、`/documents` 的整体页面设计。
- 不在本任务中直接切换生产默认版本；生产切换单独审批。

### 3.5 正式 UI 结构

桌面端以已确认字符图为准：

```text
AppShell
├─ 顶部导航：Logo / 全局搜索 / 通知 / 用户
└─ 主体
   ├─ 现有全站侧边导航
   └─ DataBrowserPage
      ├─ 页面标题 / 说明 / 收藏 / 面包屑
      ├─ 筛选条
      └─ DataWorkspace
         ├─ 指标树（纵向贯穿主表和分析区）
         ├─ 明细数据表
         ├─ 指标详情
         └─ 分析区（横跨明细表和指标详情）
            ├─ 标签：趋势 / 历史 / 修订 / 相关文档 / 指标说明
            └─ 趋势图 / 贡献分析或不可用说明 / 统计摘要
```

桌面 Grid：

```css
grid-template-areas:
  "tree table    detail"
  "tree analysis analysis";
```

宽度策略：

- `≥1440px`：指标树 240–264px，详情栏 300–316px，中间表格占剩余空间。
- `1280–1439px`：仍保持字符图要求的三列；指标树压缩至 200–220px，详情栏压缩至 260–280px，表格允许横向滚动并固定项目列。
- `1024–1279px`：指标树和详情改为抽屉，表格和分析区占主区域。
- `768–1023px`：全站导航使用现有窄屏模式；树、筛选和详情均通过按钮打开；分析区一次显示一个标签面板。
- `<768px`：表格横向滚动，指标树/筛选为侧抽屉，指标详情为底部面板；核心列保持项目、当前值和期间变化。

### 3.6 后端接口契约

#### A. 懒加载指标树

`GET /api/v1/taxonomies/{tree_code}/children`

请求参数：

- `parent_id`：空表示根节点。
- `q`：当前节点内搜索；`scope=all` 时搜索整棵树。
- `provider`、`theme`、`frequency`、`unit`、`seasonal_adjustment`：与表格一致的过滤条件。

响应：

```json
{
  "tree_code": "macro",
  "parent_id": null,
  "nodes": [
    {
      "id": "uuid",
      "code": "prices",
      "name_zh": "通胀",
      "name_en": "Prices",
      "node_type": "group",
      "icon_key": "prices",
      "has_children": true,
      "direct_series_count": 12,
      "descendant_series_count": 248
    }
  ],
  "series": []
}
```

保留现有 `GET /taxonomies/{tree_code}`，避免破坏其他消费者。新接口只取直接子节点和直接挂载指标，支持约 10,000 指标按需展开。

#### B. 浏览器表格聚合

`GET /api/v1/series/browser`

必须在 `/{series_id}` 动态路由之前声明。

请求参数：

- `q`、`node_id`、`provider`、`theme`、`frequency`、`unit`、`seasonal_adjustment`。
- `published_from`、`published_to`：筛选最新观测点的 `published_at`。
- `sort`：`taxonomy | name | current_period | current | change | period_change | yoy`。
- `order`：`asc | desc`。
- `limit`：默认 20，最大 100；`offset` 默认 0。
- `data_as_of`：可选 ISO 时间，用于复现快照。

响应：

```json
{
  "items": [
    {
      "series": {},
      "current": {"period_start": "2024-06-01", "value": 2.15, "published_at": "..."},
      "previous": {"period_start": "2024-05-01", "value": 2.38},
      "change": {"value": -0.23, "unit": "pp", "status": "available"},
      "period_change": {"value": -1.47, "unit": "%", "basis": "mom", "status": "available"},
      "yoy": {"value": 3.12, "unit": "%", "status": "available"},
      "license": {},
      "display_denied": false
    }
  ],
  "facets": {
    "provider": [{"value": "BEA", "label": "BEA", "count": 124}],
    "theme": [],
    "frequency": [],
    "unit": [],
    "seasonal_adjustment": []
  },
  "pagination": {"total": 124, "limit": 20, "offset": 0},
  "data_as_of": "2026-08-04T00:00:00Z"
}
```

实现约束：

- 先分页选出指标与唯一的已验证主数据源，再批量读取每个主数据源最近最多 420 个观测点；禁止逐行查询许可证或最新值。
- 用 SQL Window Function 或 PostgreSQL `DISTINCT ON` 获取分页、主源和最新点；批量数据进入现有 `transform_points`，不复制变换算法。
- Facet 计数采用 self-excluding 语义：计算某个维度时应用其他已选条件，但不应用该维度自身条件。
- 搜索排序：代码完全匹配 > 代码前缀 > 中英文名称 > 别名 > taxonomy/display order。
- 默认排序为 taxonomy/display order，再按名称稳定排序。
- `display_allowed=false` 时只返回可展示的元数据，不返回数值；前端显示受限状态。
- 日期筛选启用时，`published_at` 为空的最新点不命中；未启用日期筛选时可正常出现。

#### C. 指标分析聚合

`GET /api/v1/series/{series_id}/analytics`

请求参数：`start`、`end`、`transform`、`data_as_of`。

响应字段：

- `statistics`：`count`、`mean`、`median`、`min`、`max`、`stddev`、`current_percentile`。
- `next_release`：未来最早发布事件、时区、状态和角色。
- `contributions`：`available`、`reason_code`、`reason`、`target_unit`、`periods`、`components`、`reconciliation`。
- `capabilities`：display/download/AI 和各分析面板是否可用及原因。
- `data_as_of`。

如果传入快照无法复现，返回 RFC 9457 风格 `409 snapshot_unavailable`，不得静默改用 latest。

#### D. 浏览表格导出

`GET /api/v1/series/browser/export`

- 接收与 `/series/browser` 完全相同的筛选、排序和 `data_as_of`。
- 生成 UTF-8 BOM CSV，最多 10,000 条。
- 在写出第一个字节前完成全量许可证预检；任一指标不允许下载时整份返回 403。
- 403 响应列出最多 10 个受限指标名称和受限总数，不生成部分文件。

选中指标“导出数据”继续基于 `/series/{id}/observations` 的当前 `start/end/transform/vintage` 返回结果生成 CSV；按钮只有在 `download_allowed=true` 时启用，CSV 必须带 `data_as_of`、变换、单位和来源说明。

#### E. AI 能力

`GET /api/v1/ai/capabilities?series_id={id}`

响应：`configured`、`allowed`、`reason_code`、`reason`。同时检查模型配置、指标存在性、工作区访问和 `ai_context_allowed`。前端不能只依赖按钮禁用；创建 AI run 时仍需服务端再次授权。

### 3.7 数据口径

- 只使用唯一、`is_primary=true`、`mapping_status=verified` 的主数据源；多主源视为配置冲突并返回不可用原因。
- 当前值取 `data_as_of` 下最新有效观测；上期取时间序列中的前一有效观测。
- `change = current - previous`。
- 期间变化：日/周/月频使用上一期百分比变化，季频使用 QoQ，年频使用 YoY；响应通过 `basis` 明确口径。
- 同比按频率的年度间隔计算；历史不足、分母为零或缺失时返回 `null + reason_code`，不得返回 0。
- 百分比或利率指标的绝对变动使用百分点 `pp`；相对期间变化和同比使用 `%`。
- 数值精度遵循 `Series.decimal_places`；变动最多增加一位小数。
- 按已确认视觉规则，正值红、负值绿、零值中性，同时保留 `+/-` 符号，不能只靠颜色表达。
- 浏览器时区用于界面显示；tooltip 同时展示来源时区和 UTC。
- 浏览页只使用 latest 或指定 `data_as_of` 快照；历史和修订标签才展示 vintage 差异。

### 3.8 贡献分析规则

贡献图仅在以下全部条件满足时可用：

1. `data_as_of` 时点恰好存在一个生效的 `DerivedDefinition`。
2. 依赖记录明确使用 `dependency_role=contribution`。
3. 贡献已经物化为指标序列，不执行任意 `weight_expression`。
4. 公式参数声明目标变换和 reconciliation tolerance。
5. 所有组件在该期有值并通过展示许可。
6. 组件和目标之和在容差内完成 reconciliation。

多版本冲突、参数缺失、观测缺失、许可受限或 reconciliation 失败时，整个贡献图显示不可用说明，不能把缺失组件当作 0。成功时按最新完整期贡献绝对值取前 8 项，其余合并为“其他”；图表共享分析日期范围，但贡献单位不随趋势图变换，tooltip 展示真实贡献点。

### 3.9 下次发布规则

- 在未来发布事件中选择 `scheduled_at` 最早的事件。
- 同一时点有多个映射时，角色优先级：`headline > component > reference`。
- 保留 `source_timezone`，界面显示浏览器本地时间，并在 tooltip 显示来源时区和 UTC。
- 没有排期时显示“暂无已确认发布时间”，不做估算。

### 3.10 前端组件拆分

把现有页面移动为旧版组件，新页面只做编排：

```text
apps/web/app/(app)/data/page.tsx
apps/web/components/data-browser/
├─ data-browser-page.tsx          URL、选中项、feature flag 编排
├─ legacy-data-page.tsx           旧版保留一个发布周期
├─ data-browser-header.tsx        标题、面包屑、收藏
├─ browser-filter-bar.tsx         级联筛选、日期、重置、移动端入口
├─ metric-tree.tsx                ARIA tree、懒加载、节点搜索
├─ browser-table.tsx              排序、行选择、分页、横向滚动
├─ series-detail-panel.tsx        指标定义、来源、能力和动作
├─ analysis-panel.tsx             标签与独立错误边界
├─ trend-panel.tsx                趋势和时间范围
├─ contribution-panel.tsx         贡献/不可用说明
├─ statistics-panel.tsx           统计摘要
├─ history-panel.tsx              历史观测
├─ revisions-panel.tsx            修订记录
├─ related-documents-panel.tsx    相关文档
├─ browser-drawers.tsx            树/筛选/详情抽屉与底部面板
├─ browser-skeletons.tsx          区域级 loading
├─ browser-empty-states.tsx       空结果/无选择/无能力
├─ browser-query.ts               URL schema、序列化和默认值
└─ browser-format.ts              精度、单位、符号和时间格式
```

同步修改：

- `apps/web/lib/types.ts`：新增 Browser、Analytics、Facet、Capability 类型。
- `apps/web/lib/api.ts`：让 `apiFetch` 透传 `AbortSignal`，保留 RFC 9457 字段。
- `packages/sdk-typescript/src/index.ts`：新增 browser、taxonomy children、analytics、export、AI capabilities 方法和类型。
- `apps/web/components/chart.tsx`：支持文本摘要、可展开数据表、贡献图和大数据降采样。
- `apps/web/app/(app)/compare/page.tsx`：读取重复的 `series` 参数，最多预选 8 个，不自动运行。
- `apps/web/app/(app)/ai/page.tsx`：读取 `series`，加载真实指标名称，保持空 prompt；能力不足时展示原因。
- `apps/web/app/globals.css`：只补充可复用的密集表格、焦点、抽屉和数据浏览器变量，不重写全站视觉。

### 3.11 状态与 URL

URL 保存以下字段：

```text
q, series, node, provider, theme, frequency, unit,
seasonal_adjustment, published_from, published_to,
page, sort, order, tab, transform, start, end
```

规则：

- URL 是可分享状态；React Query 是服务端数据缓存；短暂的抽屉开关和 hover 不入 URL。
- 初次无 `series` 时选择当前可见第一项并用 `router.replace` 写入 URL。
- 筛选导致当前指标消失时选择新结果第一项并更新 URL；无结果时清空选中项。
- 浏览器前进/后退必须恢复筛选、分页、选中项和标签。
- 树节点选择包含全部后代指标；节点内搜索默认只搜当前节点，提供“搜索全部”。
- 表格为平铺结果，不在行内嵌套树层级。
- 先更新 URL，再由 query key 驱动请求；输入搜索使用 200–300ms debounce。

### 3.12 React Query、刷新与失败行为

- `staleTime=5min`；所有 query key 包含权限上下文、全部过滤条件、分页、排序和 `data_as_of`。
- queryFn 使用 React Query 提供的 `AbortSignal`，快速筛选时取消旧请求。
- 网络错误和 5xx 最多自动重试一次；4xx 不自动重试。
- 手动刷新执行 query invalidation；保留旧内容，拿到新 `data_as_of` 后显示“有新数据，点击更新”提示，不突然替换研究上下文。
- 树、表格、详情、趋势、贡献、修订和文档采用独立错误边界；单个区域失败不清空其他区域。
- 403 显示许可证原因；409 显示快照不可用并提供返回 latest 的显式按钮；422 保留字段错误；5xx 提供重试。

### 3.13 用户动作

- 收藏：先读取 `/me/favorites` 判断状态；未收藏 POST，已收藏 DELETE；成功后更新按钮与缓存。
- 查看历史数据：切换 `tab=history` 并滚动到分析区。
- 加入对比：跳转 `/compare?series={id}`；比较页最多读取 8 个重复参数，不自动运行。
- 导出数据：导出当前指标、当前 transform、start/end 和 data_as_of；许可证不允许时禁用并解释。
- 加入 AI 上下文：能力允许时跳转 `/ai?series={id}`，AI 页附加真实指标上下文并保持 prompt 为空。
- 趋势默认使用 `default_transform` 和最近 5 年；统计摘要始终基于同一 transform 和日期范围的完整数据。
- 修订和相关文档只有对应标签首次打开时加载。

### 3.14 图表和大数据

- 趋势图超过 5,000 点时只对可视折线执行确定性 LTTB 降采样，并保留首尾点、空值断点和异常峰值。
- Tooltip、统计、历史数据表和导出始终使用完整观测，不使用降采样结果。
- 图表提供一句文本摘要和可展开数据表；无数据、单点数据和全空值均有明确状态。
- 贡献图复用 ECharts，但不得用视觉堆叠掩盖 reconciliation 差异。

### 3.15 可访问性

- 目标 WCAG 2.2 AA；视觉截图只能检查可见风险，最终需自动化和人工键盘验证。
- 指标树使用 ARIA tree/treeitem/group；支持方向键、Home、End、Enter、展开/折叠和焦点保持。
- 表头排序按钮可聚焦并设置 `aria-sort`；数据行可聚焦，Enter 选择；收藏/查看/操作按钮各自保留独立 Tab stop。
- 抽屉和底部面板具备焦点陷阱、Escape 关闭、关闭后焦点返回触发器。
- 正负变化必须同时有符号；不得只靠红绿颜色。
- 200% 缩放不丢失核心操作；遵守 `prefers-reduced-motion`。

### 3.16 视觉验收标准

- 仅实现亮色主题。
- 1536×1024 首屏必须看见完整筛选条、至少 10 行数据、分析标签和至少 220px 高的图表内容。
- 卡片间距 `12±2px`，圆角 10–12px，筛选控件高度约 40px，表格行 38–40px，表头约 46px，分页区 48–52px。
- 区域关系必须与中文字符图一致：树纵向继续，分析区从表格列开始并横跨详情列。
- 在 1536、1280、1024、768、390 五个视口固定 fixture 截图。
- 固定状态：默认、树展开、筛选有结果、空结果、受限许可、贡献可用、贡献不可用、加载、区域错误、移动抽屉打开。
- 1536 内容区与最初参考图做同视口对比；全页截图检查 MacroLens 品牌一致性。
- 视觉问题分 P0/P1/P2/P3；交付前 P0/P1/P2 必须为 0，`design-qa.md` 写明 `final result: passed`。

### 3.17 后端测试

新增建议文件：

```text
backend/tests/test_series_browser.py
backend/tests/test_series_analytics.py
backend/tests/test_taxonomy_children.py
backend/tests/test_series_browser_export.py
backend/tests/test_ai_capabilities.py
```

覆盖：

- 搜索排名、后代节点筛选、self-excluding facets、稳定排序和分页。
- 日/周/月/季/年频的 previous、change、period_change、yoy。
- 缺失值、零分母、历史不足、百分比单位、精度和发布时间过滤。
- data_as_of 快照复现、409 行为、旧 vintage 不被修改。
- 唯一主源、多主源冲突、许可 display/download/AI 四类门禁。
- 批量查询的 SQL 次数上限，防止 N+1 回归。
- 贡献可用、版本冲突、参数缺失、组件缺失、许可受限、reconciliation 失败。
- 导出 10,000 条限制、BOM、列头、完整预检和 403 无部分响应。
- 下次发布的时间和角色优先级。

### 3.18 前端单元与组件测试

新增建议文件：

```text
apps/web/components/data-browser/browser-query.test.ts
apps/web/components/data-browser/browser-format.test.ts
apps/web/components/data-browser/metric-tree.test.tsx
apps/web/components/data-browser/browser-table.test.tsx
apps/web/components/data-browser/series-detail-panel.test.tsx
apps/web/components/data-browser/analysis-panel.test.tsx
```

覆盖 URL round-trip、默认选择、筛选移除选择、排序、分页、抽屉焦点、键盘树操作、禁用原因、错误隔离、正负值格式、空值 tooltip 和 data_as_of 新数据提示。

### 3.19 E2E 与浏览器矩阵

- 扩充 `apps/web/e2e/critical-path.spec.ts` 或拆出 `data-browser.spec.ts`。
- 流程：登录 → 展开树 → 筛选 → 选择行 → 切换趋势/历史/修订/文档 → 收藏 → 加入对比 → 返回 → 导出 → AI 上下文。
- 验证 URL 恢复、前进后退、单区域故障、许可受限、快照不可用和移动抽屉。
- Playwright 项目扩为 Chromium、Firefox、WebKit；Edge 作为 Windows 发布验收，Safari 由 WebKit 覆盖并在真实 Safari 做最终抽查。
- 浏览器支持范围：最新两个 Chrome、Edge、Firefox、Safari 主版本。

### 3.20 性能验收

- fixture 至少包含 10,000 指标、多层 taxonomy 和长达 5,000+ 点的序列。
- 1536 桌面环境 LCP ≤2.5s。
- 已缓存条件下筛选反馈 ≤300ms。
- 行选择到详情可交互 ≤500ms。
- `/series/browser` 默认 20 条的服务端 P95 ≤300ms；100 条 P95 ≤700ms。
- 页面不得为每行发起独立最新值或许可证请求。
- 表格滚动不触发整页重渲染；必要时只对表格 body 使用虚拟化，不虚拟化 ARIA tree 的当前展开层级。

### 3.21 Fixture 矩阵

测试数据必须包括：

- 日、周、月、季、年频。
- 普通数值、百分比、利率、指数单位。
- 缺失、零值、分母为零、短历史、修订、多 vintage。
- 长序列和 10,000 指标 taxonomy。
- 可展示不可下载、不可展示、不可进入 AI、需要 attribution。
- 贡献可用、冲突、缺参数、缺组件、对账失败。
- 中英文长名称、别名、重复分类、多 taxonomy 挂载。
- 有/无未来发布、有/无 AI 配置。

### 3.22 Feature flag 与兼容

- 新增 `NEXT_PUBLIC_DATA_BROWSER_V2=false`。
- Flag 关闭时普通用户继续看到旧版；管理员可用 `/data?view=v2` 预览。
- Flag 打开后默认新版；保留 `/data?view=v1` 作为一个发布周期内的管理员回退入口。
- 旧 `/series`、taxonomy 全量接口和现有 observation 接口保持兼容。
- 新 API 类型加入 SDK，不复用宽泛 `Record<string, unknown>` 作为正式契约。

### 3.23 实施任务与依赖

正式编码前创建以下任务卡；每张卡包含来源主线程、范围、成功标准、依赖和检查：

| Task ID | 责任部门 | 内容 | 依赖 | 完成条件 |
|---|---|---|---|---|
| ML-20260804-001 | Architecture/Engineering | Schema、路由契约、查询计划、快照与错误码 | 无 | 契约测试红灯，OpenAPI/SDK 评审通过 |
| ML-20260804-002 | Engineering | taxonomy children、browser、analytics、export、AI capabilities | 001 | 后端测试通过，无 N+1，许可证用例通过 |
| ML-20260804-003 | Engineering | 新版 `/data` 组件、URL 状态、响应式和跨页面联动 | 001、002 | 单元/组件测试通过，五视口可操作 |
| ML-20260804-004 | Security/Quality | 许可、权限、快照、导出、可访问性、E2E 和性能复核 | 002、003 | 无 P0/P1/P2，安全与数据审计通过 |
| ML-20260804-005 | Integration/Release | 集成、完整门禁、feature flag、变更记录 | 004 | 所有门禁通过，预览版本可回滚 |
| ML-20260804-006 | Operations | 预览环境、监控、灰度与生产切换准备 | 005 | 观察窗口满足要求，生产切换待单独批准 |

### 3.24 提交拆分

保持一个 feature branch，四个可审查提交：

1. `feat(api): define data browser contracts and tests`
   - Pydantic Schema、路由签名、TS/SDK 类型、失败测试。
2. `feat(api): implement data browser aggregation and analytics`
   - 批量查询、数据口径、贡献、导出、能力检查及后端测试。
3. `feat(web): rebuild data overview browser`
   - 页面拆分、状态、三栏布局、抽屉、跨页面联动和前端测试。
4. `test(data): add visual e2e and rollout documentation`
   - E2E、视觉基线、性能、安全复核、`design-qa.md` 和文档。

不得把数据库/API/SDK 公共契约变更与未完成前端一起直接合并到基线；由 Integration and Release 统一整合。

### 3.25 实施顺序

1. 记录当前 HEAD、工作树和六项必跑检查的基线；区分已有失败与新增失败。
2. 建立 feature flag，把当前 `/data` 移入 legacy 组件，保证随时可切回。
3. 先写后端契约和失败测试，再实现批量 browser 查询。
4. 完成 taxonomy children、analytics、export 和 AI capability，进行 SQL/许可审查。
5. 更新前端/SDK 类型和 API 客户端。
6. 建立 URL schema 与页面控制器，再实现筛选、树、表格、详情和分析区。
7. 接入收藏、对比、导出、AI、历史、修订和文档。
8. 完成响应式、键盘、图表摘要、降采样和独立错误边界。
9. 运行单元、契约、E2E、性能和安全检查。
10. 在 1536/1280/1024/768/390 捕获固定状态截图并执行设计 QA；修复所有 P0/P1/P2。
11. 管理员预览一个完整验证批次；确认日志、错误率、P95 和许可证审计。
12. 合并后保留旧版一个发布周期；生产默认切换另行批准。

### 3.26 必须执行的验证

```bash
ruff check backend
mypy backend/src
pytest backend/tests
npm --workspace apps/web run lint
npm --workspace apps/web run test
npm --workspace apps/web run build
npm --workspace apps/web run typecheck
npm --workspace packages/sdk-typescript run typecheck
npm --workspace apps/web run e2e
```

执行要求：

- 开始前保存基线结果；历史失败必须明确列出。
- 改动路径不得新增 lint、type、test 或 build 错误。
- 若 Vitest 运行器本身存在基线 ESM 问题，只修复阻塞本功能验证的最小配置并单独记录。
- 生产构建必须通过；仅 HTTP 健康检查不能替代浏览器验证。

### 3.27 上线观察与回滚

- 先以 flag 关闭部署，管理员 `?view=v2` 验收。
- 至少观察一个完整数据验证批次和一个工作日，期间不得出现 P0/P1。
- 观察：API 5xx/4xx、browser P50/P95、查询数、数据库慢查询、导出 403、快照 409、客户端错误、抽屉/筛选关键事件。
- 出现以下任一条件立即关闭 flag：许可证泄漏、数值计算错误、核心流程失败率 >1%、P95 连续 15 分钟超过预算。
- 回滚只切换页面版本或应用版本，不回滚、删除或重建 observation vintage。
- 生产默认切换、旧版删除和服务器部署分别审批。

### 3.28 完成标准与停止规则

只有同时满足以下条件才可报告实现完成：

- 中文字符图中的所有区域和动作均已实现或有明确、经确认的不可用说明。
- 新接口、前端类型和 SDK 契约一致。
- 表格、趋势、统计、贡献和导出共享 `data_as_of`。
- 许可门禁在 display、download、API redistribution 和 AI 四个路径均有自动化测试。
- 六项项目必跑检查与新增 typecheck/E2E 通过，或只剩书面确认的历史基线问题。
- `design-qa.md` 为 `final result: passed`，P0/P1/P2 为 0。
- Feature flag 可切回旧版，回滚不触碰 vintage 数据。

如果关键事实不可获得、快照无法复现或贡献定义不满足条件，应显示并记录阻塞原因；不得通过猜测、填 0、静默 latest 或绕过许可证来“完成”页面。

## 4. 使用的 Agents、Skills、Tools 与文档

- Agents：未派发子 Agent；用户本轮要求的是计划，没有进入并行实现。
- Skill：用户指定的 `gpt-plan`。
- Tools：本地文件检索、源代码读取、Git 状态检查、补丁写入。
- 阅读文档与代码：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、数据页、AppShell、图表、API、Schema、服务、模型、SDK、Vitest/Playwright 与 E2E 文件。
- 设计依据：用户确认的中文 UI 字符图，以及最初的 1536×1024 视觉参考图。

## 5. 值得沉淀的经验与模式

- 对数据密集型页面，视觉重构之前先定义聚合读模型，能避免前端请求瀑布和数据口径分裂。
- 结构图、视觉参考和现有设计系统必须明确优先级，否则实现者会用某一份材料覆盖另一份已确认决策。
- `data_as_of` 应成为浏览、分析、统计、贡献和导出的共同主键式上下文，而不是只显示在页面上的文字。
- 许可证不是按钮状态，而是查询、响应、导出、AI 和缓存键共同遵守的能力模型。
- 完整计划需要把断点、错误、空状态、权限、性能和回滚写成验收规则，不能只列组件清单。

## 6. 更好的初始提示词

> 请基于我提供的中文 UI 字符图和视觉参考截图，为 MacroLens `/data` 页面制定完整实现计划。字符图决定页面结构，截图决定视觉密度，现有 MacroLens 组件决定品牌。计划必须先检查现有前后端代码，再覆盖 API 契约、数据口径、组件拆分、URL 状态、桌面/移动响应式、许可和快照规则、贡献分析、导出、收藏/对比/AI 联动、自动化测试、视觉验收、性能预算、feature flag 和回滚。只出计划，不改业务代码；计划要细到另一名开发者无需再做产品决策即可实施。

## 7. 更优方案与提示词

更优方案是在计划确认后先实现“契约 + 固定 fixture + 视觉基线”垂直切片，用一个真实指标贯通树、表格、详情、趋势、贡献不可用说明和导出，再扩展到完整数据量。这样能够最早暴露口径、许可和布局冲突，同时保留分阶段回滚能力。

> 请按已确认的数据概览实施计划先完成一个受 feature flag 保护的垂直切片：只使用固定 fixture 和一个真实指标，贯通 taxonomy children、series browser、analytics、详情、趋势、统计、贡献不可用说明、收藏、对比、导出和 AI 能力；同步完成 1536/1280/390 三个视口的视觉基线和许可证测试。切片通过后再扩展到全部筛选、10,000 指标性能、五视口和完整跨浏览器矩阵。每阶段都保持旧版可切回，不修改任何既有 observation vintage。
