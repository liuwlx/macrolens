# ML-20260804-002 Engineering-02 工作报告

## 1. 问题与场景

Windows 开发机需要运行真实 MacroLens API/Web，同时复用 `111.229.152.122` 上现有 PostgreSQL。数据库不能暴露公网端口，开发流程不能启动迁移、种子、Worker 或调度器，也不能复用生产应用凭据。脚本还必须在已有设计预览服务占用 3000/4010 时安全切换，并避免 PID 复用导致误杀。

## 2. 分析过程

先核对项目 Compose、API 配置、Alembic head、Python/Node 版本约束和忽略规则，再按安全预审收紧权限。远端 PostgreSQL 容器只能通过 Compose project/service、健康状态和 `macrolens_default` 网络共同定位；SSH 隧道只监听 `127.0.0.1:15432`。数据库角色采用“所有业务表只读、仅 app 业务表 DML、audit_log 只追加、observation_vintage 明确只读”的权限模型，并拒绝角色成员关系和对象所有权。

进程管理不能只保存 PID，因此状态同时保存启动时间、绝对可执行文件路径、角色和命令行 SHA-256。启动前对未知端口占用立即失败；已知 `local-preview-server.mjs` 只做身份校验，直到远端容器、隧道和 Alembic 版本均通过后才停止。

## 3. 解决流程

1. 新增 `scripts/remote-dev.ps1`，提供 Provision/Start/Status/Stop/Deprovision 五个动作。
2. Provision 发现本机 Python 3.12 与 Node.js 22，创建独立数据库密码和 JWT secret，经 SSH 标准输入原子配置最小权限角色，并用 Windows ACL 保护 `.env.remote`。
3. Start 创建/复用项目 `.venv` 并补齐 backend 运行依赖，建立 SSH 隧道，读取远端 `alembic_version` 与本地 head 比较；通过后启动真实 Uvicorn 与 Web dev server。
4. Stop/Status 依据 PID、StartTime、ExecutablePath 和命令行 SHA-256 校验进程身份。
5. 新增静态与本地行为测试，并在 README 记录使用方式和安全边界。

## 4. Agents、skills、tools 与文档

- Agents：主线程 `/root` 负责任务卡、两轮安全审查和验收协调；部门线程 `/root/engineering_02` 负责实现与本地验证。
- Skills：部门实现未额外调用 skill；沿用主线程经 `gpt-plan` 形成的实现任务卡和项目组织流程。
- Tools：`apply_patch` 用于所有文件修改；PowerShell/`exec_command` 用于只读检索、解析、静态测试、Node/Python 发现和 Git 检查；`send_message` 用于向主线程同步 P0 修正状态。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`docker-compose.yml`、`infrastructure/server/docker-compose.yml`、`.env.example`、`.gitignore`、`README.md`、`backend/pyproject.toml`、`backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/versions/0001_initial.py`、API 配置和根 `package.json`。

## 5. 可沉淀经验

- 远程开发数据库应使用回环 SSH 隧道和独立、可撤销的最小权限角色，而不是开放数据库端口或复用生产凭据。
- 容器发现必须组合 project、service、health 和 network，不应依赖易变化的容器名/IP。
- 远端 schema 兼容性应先做只读版本比较；开发辅助脚本不应隐式迁移生产数据库。
- Windows 进程回收应以 PID、启动时间、可执行文件和命令行哈希组成复合身份。
- 替换已知占用进程应分“提前验证”和“最后执行”两阶段，避免前置检查失败造成不必要中断。

## 6. 更好的初始提示词

请为这个项目实现一个 Windows PowerShell 5.1 远程数据库开发脚本：本地启动真实 API 和 Web，通过 `ubuntu@111.229.152.122` 的 SSH 隧道连接现有 Compose PostgreSQL，数据库只映射到本机 `127.0.0.1:15432`。提供 Provision/Start/Status/Stop/Deprovision；使用独立最小权限数据库角色和独立 JWT，密码只保存到 gitignored 且 ACL 受限的 `.env.remote`。动态校验 Compose project/service/healthy/network，比较远端 Alembic 版本但绝不运行迁移、seed、worker 或 scheduler。要求项目 `.venv` Python 3.12、自动发现可用 Node.js 22，并用 PID+启动时间+exe+命令行哈希安全管理进程。只做本地/静态测试，不实际连接或修改远端，最后提交部门 commit 和工作报告。

## 7. 更优方案反思与提示词

更优方案是把数据库权限 SQL 独立成可审计模板，并为进程/端口判断拆出可注入的纯函数与 Pester 单元测试；同时由服务器侧预置并轮换开发角色，客户端 Provision 只获取短期凭据。这样能减少客户端持有数据库管理员能力，并提升权限回归测试质量。

更优提示词：请先设计“服务器侧一次性最小权限角色配置 + 客户端无管理员权限启动器”的两段式方案。服务器侧脚本只允许管理员人工执行并输出短期开发凭据；客户端 PowerShell 5.1 脚本只建立回环 SSH 隧道、校验 Alembic 版本、创建 Python 3.12 `.venv`、发现 Node.js 22、启动 API/Web 和安全回收进程。把权限 SQL、端口分类和进程身份校验拆成可单测模块，提供 Pester 测试，任何测试都不得触碰远端。
