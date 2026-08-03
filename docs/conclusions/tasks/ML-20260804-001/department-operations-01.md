# ML-20260804-001 Operations 本地验收报告

## 1. 问题与场景

任务需要一个可点击、完整运行的数据浏览器验收入口，但任务卡明确禁止未经单独批准切换生产 feature flag 或部署服务器。因此验收环境必须在本机启动，并使用稳定、可复现的数据快照。

## 2. 分析过程

先尝试使用项目 Docker 依赖，宿主机的 WSL/虚拟化引擎不可用，无法形成可靠容器栈。为继续验证 UI 和核心交互，改为使用仅监听本机的 fixture API，并让 Next 本地实例显式指向该 API、开启 V2 验收开关。

## 3. 解决流程

1. 新增 `artifacts/design-qa/mock-api.mjs`，覆盖认证、通知、收藏、taxonomy、browser、analytics、observations、revisions 和 export 等验收调用。
2. 在 `http://localhost:4010/api/v1` 启动 fixture API。
3. 在 `http://localhost:3000/data` 启动 Web 验收实例，显式设置 `NEXT_PUBLIC_DATA_BROWSER_V2=true` 和本地 API 地址。
4. 用内置浏览器完成登录态加载、四视口、抽屉、树、筛选、分页、排序、tabs、回滚入口和 console 验收。
5. 精确清理 Next 自动生成的 `tsconfig.json` / `next-env.d.ts` 副作用，保持 Git 工作区只包含批准的报告变更。

## 4. Agents、Skills、Tools 与文档

- Agent：由 PRIMARY `/root` 代行 Operations；未占用额外部门席位。
- Skills：Product Design image-to-code、browser control。
- Tools：`exec_command`、`apply_patch`、Node REPL browser、`view_image`、端口/PID检查。
- 文档：组织规则、任务卡、`design-qa.md`、Quality/Integration 报告、两张视觉参考图。

## 5. 沉淀经验

- Docker 不可用时，本地固定 fixture 可以继续完成 UI/交互验收，但必须明确它不等价于真实生产数据集成。
- 长驻预览必须绑定精确端口和工作区进程；停止或重启前应验证 PID 命令行属于当前项目。
- 本地 feature flag 只用于验收，不能被描述为生产切换。

## 6. 更好的初始提示词

> 请为当前数据浏览器启动一个仅本机可访问的验收环境；若 Docker 不可用，就使用覆盖当前页面全部调用的固定 fixture API。Web 显式指向本地 API 并开启 V2 验收开关，完成 390/768/1024/1280 四视口和核心交互/console 检查，清理 Next 生成副作用，给出可点击 localhost 链接，但不要部署或切换生产开关。

## 7. 更优方案与提示词

更优方案是在 CI 中提供带最小 PostgreSQL seed 的可复用 review environment，同时保留 deterministic mock 作为视觉回归层；这样既能稳定截图，也能补真实 vintage/interval SQL。

> 请建立两层验收：第一层使用 deterministic mock API 做像素、响应式和交互回归；第二层用临时 PostgreSQL seed 验证真实 taxonomy、vintage cutoff、主源冲突、许可和排序 SQL。两层共享同一 Web build 和测试身份，全部通过后才生成本地/Review App 链接；任何环境副作用必须在提交前清理。

## 验收结果

- 本地入口：`http://localhost:3000/data`
- Fixture API：`http://localhost:4010/api/v1`
- Web console errors/warnings：0
- `design-qa.md`：passed
- 生产部署/feature flag 切换：未执行
