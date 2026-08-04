# MacroLens 远程数据库开发与全宽运行态验收报告

- 任务：`ML-20260804-002`
- 最终代码基线：`dd0f23bf876ab3011111931973ee217930f688cc`
- 范围：登录后全宽布局、Windows 远程数据库开发工具、真实运行态与故障恢复验收
- 最终结论：任务范围内 Quality PASS、Security PASS；本轮仅提交知识报告，不 push、不部署、不停止现有服务。

## 1. 问题与场景

本次工作同时解决两个直接影响本地真实开发的问题。

第一，MacroLens 登录后的 AppShell 把主内容限制在 `1720px` 内，2560px 超宽屏出现大面积无效留白；数据浏览器桌面网格又使用固定行高，无法吸收高视口剩余空间。目标是在不改变移动端与 1280px 以下布局的前提下，让后台页面占满可用宽度，并让数据页在桌面端按约 3:2 使用剩余高度。

第二，Windows 开发机需要运行真实 Web/API，但复用服务器 `111.229.152.122` 上的 PostgreSQL。数据库不能暴露公网端口，不能复用生产应用凭据，启动器不能隐式迁移、seed、启动 Worker/调度器，也不能误杀已有本地预览。脚本必须提供 Provision、Start、Status、Stop、Deprovision 五个动作，通过 `127.0.0.1:15432` 回环 SSH 隧道访问数据库，并以独立、可撤销的最小权限角色运行。

真实运行验收连续暴露了四个跨层问题：Windows OpenSSH 丢失 Docker Go template 内层引号；空 `.venv` 缺依赖时 PowerShell 5.1 在读取退出码前被 native stderr 终止；通用 native 命令失败输出既被截断又可能泄露敏感信息；SQLAlchemy 的 `postgresql+psycopg://` URL 被直接交给原生 psycopg，且开发角色缺少只读 `alembic_version` 权限。另有本地验收服务依附临时会话，导致浏览器出现 `ERR_CONNECTION_REFUSED`。

## 2. 分析过程

### UI 与几何

先拆分 AppShell 和页面自身的责任：主内容最大宽度属于 Shell，数据浏览器纵向分配属于页面。桌面可用高度按顶栏 68px、main 顶部 24px、底部 32px计算为 `100dvh - 124px`。静态 CSS/Vitest 锁定无 max-width、16/24px padding 和桌面 `minmax` 规则；Playwright 再量测 document 宽度、页面边界、两行高度、内部滚动与底部空白，避免仅凭截图判断。

### 远程数据库与安全边界

远端 PostgreSQL 只通过 Compose project/service、healthy 状态和 `macrolens_default` 网络联合定位。SSH 使用已知 host key、BatchMode 和回环端口转发；数据库不映射公网端口。专用角色采用“业务表默认 SELECT、`app` schema 所需 DML、`audit.audit_log` 只追加、`data.observation_vintage` 明确禁止写、`public.alembic_version` 仅 SELECT”的权限模型，并禁止 superuser、createdb、createrole、inherit、replication、bypassrls、角色成员关系和对象所有权。

进程管理不能只依赖 PID，因此状态记录 PID、启动时间、绝对 executable、角色和命令行 SHA-256。已有 3000/4010 预览仅在完整远端校验之后、且 PID/exe/命令行/双端口全部匹配时才允许替换；未知监听器一律 fail closed。

### R1–R4 诊断闭环

- R1（main `4c7e17a`）：错误 `function "macrolens_default" not defined` 表明 Go template 引号跨 PowerShell/OpenSSH/remote shell 丢失。修复为无嵌套引号的 `networkName=IPAddress` 输出，并在本地只接受唯一规范 IPv4；真实 SSH 只读 `Get-RemotePostgres` 通过。
- R2（main `da57804`）：空 `.venv` 缺模块是预期分支，不应以 traceback 表达。依赖探测改用 Python 内部专用退出码 3，只在最小 try/finally 范围临时放宽 EAP，其他退出码 fail closed。
- R3（main `22d5496`）：将 native stderr 与成功状态解耦，统一按退出码决定结果；失败异常不回显捕获内容。pip 增加 timeout/retries/no-input，并只输出 network、disk-space、permission、resolution、package、build 等有限类别。
- R4（main `dd0f23b`）：SQLAlchemy URL 与 libpq conninfo 不能混用。Alembic 探针只把 `postgresql+psycopg://` 严格转换为 `postgresql://`，其余凭据、主机、端口、库名和 query 原样保留；临时环境变量在 finally 删除。角色只新增 `public.alembic_version` SELECT，Deprovision 对称撤销。

### 运行态证据

最终运行态 Status 验证 tunnel、API、Web 三类受管进程均通过复合身份校验，回环隧道与本地 API/Web 端口处于预期状态。HTTP 验收确认 Web 数据页和 API 可访问，真实 API 通过隧道读取远程 PostgreSQL 数据而非 mock；数据读路径、应用写权限、audit append-only、observation vintage 禁写和 Alembic 元数据只读边界均按预期工作。

隧道/启动失败恢复也经过实际故障链验证：远端发现、依赖安装、Alembic 探针任一步失败时，不继续启动后续服务；Start catch 会回收本轮已创建的 tunnel/API/Web 子进程，状态文件不被错误提交，已知设计预览在远端校验完成前不会被停止。修复后可重新 Start 并恢复 Status/HTTP/数据检查。连接拒绝问题则通过独立后台预览进程、端口/PID/命令行核验和连续两轮 HTTP 检查闭环。

## 3. 解决流程

1. 冻结任务边界：不开放数据库公网端口，不运行迁移/seed/Worker/scheduler，不复用生产应用凭据。
2. UI 候选移除 AppShell `max-w-[1720px]`，保留移动 16px/桌面 24px padding；数据页在 `>=1280px` 使用 viewport flex 和 `minmax(500px, 3fr) minmax(300px, 2fr)`。
3. 新增 `scripts/remote-dev.ps1` 五动作、README、PowerShell static/Pester 测试和部门报告。
4. Provision 生成独立数据库/JWT secret，原子设置最小权限角色，并用 Windows ACL 保护 ignored `.env.remote`。
5. Start 发现 Python 3.12/Node 22，准备项目 `.venv`，只读发现远端容器，建立回环 SSH 隧道，比较远端/本地 Alembic head，再启动真实 API/Web。
6. Status/Stop 用复合进程身份判定；Deprovision 对称撤销单表/Schema/数据库权限并删除专用角色。
7. 通过 R1–R4 分别关闭 Docker inspect 引号、空 venv 依赖探测、native stderr/秘密泄露、psycopg URL/Alembic 权限问题。
8. 运行 PowerShell static/Pester、真实 SSH 只读发现、Node 22 focused/full Web tests、changed ESLint、production build 和六视口 Playwright；每次集成均执行 `git diff --check` 并清理 Next 生成副作用。
9. 运行态完成 Status、HTTP、真实数据、权限、隧道失败恢复与重新启动验收；最终 main 固定为 `dd0f23b`。
10. 本轮仅沉淀本报告，不停止当前服务，不触碰两个未跟踪文件或 ignored `.env.remote`/`.venv`。

## 4. Agents、Skills、Tools 与文档

### Agents

- `/root`：任务卡、真实运行故障反馈、运行态验收、Quality/Security 收口与最终知识整理指令。
- `engineering-01`：AppShell 全宽、数据浏览器 viewport 几何、Vitest/Playwright。
- `engineering-02`：remote-dev 五动作及 R1–R4 修复、PowerShell/Pester/真实只读 SSH 验证。
- `integration-release-01`：逐提交白名单集成、哈希保护、门禁、副作用清理和本报告提交。
- Quality/Security：对 UI 几何、脚本安全边界、最小权限、秘密处理与运行态证据给出任务范围内 PASS。

### Skills

本轮最终知识沉淀未使用任何显式 skill。报告基于已提交代码、部门报告、运行态证据和主线程验收结论整理；没有在本轮重新触发诊断、浏览器或安全扫描 skill。

### Tools

- `exec_command` 与 PowerShell：Git、哈希、端口/进程、HTTP、静态测试、运行时状态和构建门禁。
- SSH、Docker、PostgreSQL：只读容器发现、回环隧道、真实数据与最小权限验收。
- Playwright：390、768、1280、1440、1920、2560 六视口几何验收。
- Pester：PowerShell 合同、fake native process、错误策略恢复和秘密不泄露回归。
- `apply_patch`：源码修复、测试与结论报告。
- collaboration 与 plan：部门交付、候选 SHA、R1–R4 调度和状态同步。

### 读取的主要文档

- 根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`。
- `README.md`、`scripts/remote-dev.ps1`、static/Pester/remote-readonly tests。
- `department-engineering-01.md`、`department-engineering-02.md`、R1–R4 报告和 `department-integration-release-01.md`。
- `docs/conclusions/2026-08-04-local-preview-connection-refused-fix.md`。
- backend Alembic/配置、Compose 和既有数据安全规则。

## 5. 值得沉淀的经验与模式

1. 跨 PowerShell、OpenSSH、远端 shell、Docker template 的命令应避免嵌套引号；优先输出简单无歧义记录，再在本地做唯一性和类型校验。
2. Windows PowerShell 5.1 的 native stderr 不是失败判据，退出码才是；EAP 放宽必须限制在最小 try/finally，并在所有路径恢复。
3. 敏感自动化默认不应回显失败输出。通用命令只报告 executable/exit code；特定工具输出先映射为有限、不含秘密的诊断类别。
4. SQLAlchemy driver URL 与原生 DBAPI/libpq URL 是不同接口；转换必须发生在调用边界，严格校验 scheme，其他字符逐字保留。
5. 健康检查权限也必须最小化。Alembic 只需要 `public.alembic_version` SELECT，不应因此开放 public 其他对象或写权限。
6. 安全停止进程需要 PID、StartTime、ExecutablePath、命令行哈希和端口归属共同证明，不能凭端口或 PID 单点判断。
7. Start 应按“发现→依赖→隧道→schema→替换旧预览→API→Web”排序，并在异常时回收本轮子进程；这样失败不会破坏仍可用的旧验收入口。
8. 宽屏 UI 不能只做截图目测；根 scrollWidth、内容边缘、grid 行高比例、底部差值和内部 scroller 都应成为自动化断言。
9. 本地可点击链接是运行时交付物。交付前要连续验证进程、监听端口、HTTP、关键内容和依赖 API，不能只报告“构建成功”。
10. 全量 lint 的 52 errors / 4 warnings 位于本次白名单外，是已知技术债而非本轮回归；changed-path lint、tests、build、Playwright、PowerShell/Pester 和 Quality/Security PASS 共同支持本次非阻断判定，但技术债仍需单独清理。

## 6. 更好的初始提示词

> 请一次完成 MacroLens 的 Windows 真实本地开发与超宽屏验收。登录后 AppShell 移除 1720px 最大宽度，保持移动16px/桌面24px padding；数据页在 >=1280px 使用 `100dvh` 扣除 Shell chrome 后的剩余高度，两行至少500/300px并约3:2，390到2560px无根横向溢出。新增 PowerShell 5.1 工具提供 Provision/Start/Status/Stop/Deprovision：通过 `ubuntu@111.229.152.122` 和仅绑定 `127.0.0.1:15432` 的 SSH 隧道连接现有健康 Compose PostgreSQL；使用独立、可撤销最小权限角色和独立 JWT，`.env.remote` 必须 gitignored 且 ACL 受限。远端容器用 project/service/health/network 唯一定位；禁止公网5432、迁移、seed、Worker、scheduler和复用生产凭据。依赖探测、native stderr、pip 错误分类、SQLAlchemy→psycopg URL、Alembic 单表只读权限、PID复合身份和失败回收都要有 PowerShell/Pester 测试。完成六视口 Playwright、Web tests/build、真实 Status/HTTP/数据/权限/隧道恢复验收、Quality/Security 复核和七节报告；不要 push 或部署。

## 7. 一次解决的更优方案提示词

当前脚本已经可用，但长期更优方案是把“服务器侧权限配置”和“客户端日常启动”彻底分离，并把副作用变成可审计执行计划。服务器管理员一次性创建短期/可轮换开发凭据；客户端永远不持有管理员数据库权限。连接配置由结构化对象同时生成 async SQLAlchemy URL、sync SQLAlchemy URL 和原生 psycopg conninfo，避免字符串 replace。外部进程统一使用 `System.Diagnostics.Process`，支持参数安全、stdout/stderr 分离、超时、取消和秘密净化。

> 请将 MacroLens remote-dev 重构为两层：服务器侧管理员脚本只负责原子创建/轮换/撤销短期最小权限角色，输出受控凭据；客户端 PowerShell 无管理员权限，只做运行时发现、回环 SSH 隧道、只读 Alembic 比较和本地 API/Web 生命周期。所有动作先生成结构化 execution plan，只有显式 `-Execute` 才产生副作用；SSH、Docker、PostgreSQL 和 Process 通过可注入适配器实现。使用统一连接配置对象生成 async/sync SQLAlchemy URL 与原生 psycopg conninfo；使用 `System.Diagnostics.Process` 实现安全参数、分流输出、超时、取消和秘密策略。Pester 全 mock 覆盖五动作、权限矩阵、失败回滚、PID复合身份、大输出和 secret canary；再用临时服务器角色做审批式 smoke。UI 同时抽取 AppShell chrome CSS变量和通用 viewport page，跑 Chromium/Firefox/WebKit 390–2560px 几何门禁。全量 lint 技术债单独建任务清零后，才把该工作流升级为默认开发入口。

## 验收结论与残余风险

- 最终 main：`dd0f23bf876ab3011111931973ee217930f688cc`；R1–R4 均已集成并通过 PowerShell static/Pester/diff check。
- UI：Vitest 8 files / 19 tests，六视口 Playwright 6 passed；2560x1280 document width 2560、左右各24px、grid 约3:2、底部空白32px。
- 运行态：Status、HTTP、真实数据、最小权限、回环隧道与失败恢复通过；任务范围内 Quality PASS、Security PASS。
- 全量 lint 仍有白名单外既有 52 errors / 4 warnings，本轮按已审查非回归处理，不代表仓库 lint 债已清零。
- 真实远程开发角色允许 `app` 业务写入；使用者仍需遵守 workspace、vintage append-only 和许可规则，避免把开发验收当成隔离测试数据库。
- `.env.remote` 是本地长期凭据文件，即使 gitignored/ACL 受限，仍应定期轮换并在不用时 Deprovision；主机密钥、sudo docker 和远端 Compose 标签变化都会使启动 fail closed。
- 浏览器几何证据以 Chromium 为主；Firefox/WebKit 尚未成为本任务的强制门禁。
- 本轮未停止现有服务、未 push、未部署，也未修改两个未跟踪文件或 ignored `.env.remote`/`.venv`。
