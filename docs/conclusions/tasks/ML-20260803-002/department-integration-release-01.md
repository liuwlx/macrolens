# ML-20260803-002 集成发布部 01 回执

- 席位状态：REVIEW
- 任务 ID：ML-20260803-002
- 来源主线程：`/root`
- 起始提交：`79eca99e8752a0e467856bf02b971e40e7eac6fb`
- 完成结果：完成生产部署变更的白名单审查、依赖锁定复核、前端生产构建复核和单提交集成；未推送、未部署。
- 修改文件：仅本任务授权的 Web 依赖与最小类型修复、根锁文件、服务器部署配置及任务卡/部门回执。
- 提交 SHA：本报告随集成提交写入，最终 SHA 在主线程交付回执中提供。

## 1. 问题与场景

服务器部署需要把一个可复现的 MacroLens 发布候选绑定到固定源码基线，同时避免把共享工作区中的 Next.js 构建产物、真实秘密或其他任务文件混入提交。初始候选还存在 npm peer 冲突、缺少根锁文件、报告页构建期类型错误，以及裸服务器部署所需的 Compose、生产环境模板和 Nginx 入口尚未进入版本控制等问题。

## 2. 分析过程

先以 `git status --porcelain=v2`、工作区差异和未跟踪文件建立完整变更清单，再按任务卡白名单逐个审查。依赖层面确认 `echarts-for-react@3.0.6` 的 peer 范围包含 `echarts@6.0.0`，根 `package-lock.json` 为 lockfile v3，且映射根、Web 与 SDK 工作区。代码层面确认报告页只把无参 mutation 调用改为显式传入 `undefined`，保持运行语义不变。部署层面确认 API、Web 与 MinIO 仅绑定回环地址，自有镜像使用 `RELEASE_SHA` 标签，生产示例只包含占位符，Nginx 统一代理 Web、API 与对象存储路径。

构建复核发现本机 Node 为 20.11.1，低于项目声明的 Node 22；npm 依赖解析和 Next 生产构建仍成功，但正式镜像构建必须继续使用 `apps/web/Dockerfile` 中的 Node 22。Next 构建自动生成的 `next-env.d.ts` 和对 `tsconfig.json` 的格式/include 改写已在提交前清理。

## 3. 解决流程

1. 完整读取组织规则、部署文档、任务卡和研发/测试回执。
2. 记录 `main` 基线、全部 tracked/untracked 变更和忽略产物。
3. 逐项审查包版本、锁文件工作区、报告页最小修复、Compose、Nginx 与生产环境示例。
4. 扫描允许文件中的私钥、访问令牌和硬编码密码模式；仅发现 Compose 环境变量引用。
5. 运行 `npm ls` 和 package-lock-only dry-run，确认 peer 树可解析且锁文件未变化。
6. 使用 `NEXT_PUBLIC_API_URL=/api/v1` 重跑 Web 生产构建，确认编译、TypeScript 和页面生成通过。
7. 清理本次构建产生的 Next 临时源文件副作用。
8. 仅显式暂存任务白名单，运行 staged diff、秘密和 whitespace 检查后创建单一集成提交。

## 4. Agents、skills、tools 与文档

- Agents：集成发布部 01；未创建或调用子 Agent。
- Skills：未使用专用 skill；本任务是项目内 Git 白名单集成与发布门槛复核。
- Tools：`exec_command` 用于只读审查、npm 检查、构建和 Git 集成；`apply_patch` 用于清理构建副作用并生成本回执；`send_message` 用于与主线程同步临时部署文件边界。
- 已读文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/deployment.md`、`docs/acceptance.md`、`docs/operations-runbook.md`、本任务卡、研发部 01 回执、测试部 01 回执，以及本次允许提交的全部源码、锁文件和部署配置。

## 5. 值得沉淀的经验

1. 共享工作区集成必须使用显式路径暂存，并在提交前后分别核对 `git status` 与 staged name-status。
2. `NEXT_PUBLIC_*` 是构建期合同；生产 Web 镜像必须在构建时注入同源 `/api/v1`，仅在容器运行环境中设置不会修复客户端包。
3. 锁文件解决的是依赖树可复现性，镜像的可追溯性还需要 release SHA、Image ID 和 RepoDigest 三者共同留档。
4. Next 生产构建会改写类型配置和生成辅助文件；构建成功后仍须进行范围审计，不能把生成副作用顺手提交。
5. 示例环境文件应使用清晰占位符并保持可跟踪命名；不要用会被 `.env.*` 规则忽略的文件名，也不要强制提交被忽略的秘密文件。

## 6. 更好的初始提示词

> 请从当前 `main` 的确切 SHA 为 MacroLens 准备一个裸 Linux 服务器部署提交：先完整列出所有工作区变更，只接收 Web 构建阻断的最小依赖/类型修复、根 npm 锁文件、服务器 Compose/Nginx/无秘密环境示例和本任务文档。确认 Web 构建时使用 `NEXT_PUBLIC_API_URL=/api/v1`，自有镜像标签绑定源码 SHA，内部端口仅监听回环。使用 Node 22 从锁文件复核 peer 依赖并执行生产 build，清理 Next 自动生成副作用，扫描真实秘密，最后只显式暂存白名单、运行 staged `git diff --check`，创建一个不推送的清晰提交并返回 SHA 与检查证据。

## 7. 当前场景的更优方案与提示词

更优方案是在干净的 Node 22 构建环境中以 `npm ci` 重建依赖，并把服务器部署配置与源码在同一提交中版本化；随后在服务器构建两个带该提交 SHA 的镜像并记录 digest。这样本地提交、镜像、运行配置和回滚对象形成一条完整证据链，而不是依赖共享工作区中已有的 `node_modules`。

> 请在干净的 Node 22 环境中检出 MacroLens 指定基线，应用且仅应用已批准的 Web 最小修复与服务器部署配置；用根锁文件执行 `npm ci`、peer 树检查和生产 build，验证 Compose/Nginx 与占位符环境模板，确认没有构建产物或秘密进入 Git。创建单一集成提交后，在服务器从该 SHA 构建 backend/web 镜像，记录 Image ID、RepoDigest、迁移版本、配置哈希和回滚镜像，再执行上线验收。

## 风险与交接

- 本机复核使用 Node 20.11.1，npm 返回 engine warning；正式容器构建必须以 Node 22 再验证。
- 锁文件的 resolved URL 来自当前配置的 npm 镜像源并带 integrity；生产构建环境需能访问该源，或在受控变更中重新生成并复核锁文件。
- 服务器证书、镜像 digest、数据库备份、容器健康和外网关键路径属于部署时门槛，不由本次 Git 集成提交代替。
- 不得删除旧数据卷或执行破坏性 down migration；应用回滚使用上一镜像，数据发布回滚使用上一 publication batch。
