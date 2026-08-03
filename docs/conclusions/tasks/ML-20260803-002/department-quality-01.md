# ML-20260803-002 测试部 01 上线预检报告

- 席位状态：REVIEW（本地预检已完成，外网运行态验收待部署候选可用后执行）
- 任务 ID：ML-20260803-002
- 来源主线程：`/root`
- 实际范围：只读复核仓库与服务器部署候选，运行本机可执行的静态门禁，输出外网上线验收清单；未修改业务代码、部署配置或服务器状态。
- 基线：`main@79eca99e8752a0e467856bf02b971e40e7eac6fb`

## 1. 问题与场景

本任务要把当前 MacroLens 部署到 `111.229.152.122`，并提供可外网验收的完整运行链接。测试部需要在不等待服务器构建、不修改业务文件的条件下，独立确认仓库有哪些可执行门禁、部署候选是否满足基础契约，以及上线后必须验证哪些功能。

当前本机没有项目 `.env`、`node_modules` 或 Python 虚拟环境，Docker CLI 可用但 Docker Desktop 引擎未运行。宿主默认 Python 为 3.11、Node 为 20；项目实际要求 Python 3.12+、Node 22+。系统另有 Python 3.12，可用于纯语法检查。

## 2. 分析过程

1. 完整读取组织规则、任务卡与 `docs/acceptance.md`，确认测试部范围和上线成功标准。
2. 阅读根 `docker-compose.yml`、`.env.example`、前后端 Dockerfile、Python/Node 项目清单、生产配置守卫、API 中间件和 Playwright 关键路径。
3. 检查本机 Python、Node、npm、Docker、依赖目录与 `.env` 状态。
4. 使用临时目录中的环境文件解析根 Compose，避免向仓库写入 `.env`。
5. 对并行产生的 `infrastructure/server` 部署候选做只读复核，并使用临时环境文件解析其 Compose。
6. 执行 Python 3.12 `compileall` 和 `git diff --check`；尝试执行仓库校验器并记录真实阻塞原因。

## 3. 解决流程与检查结果

### 已执行

| 检查 | 结果 | 证据/说明 |
|---|---|---|
| `py -3.12 -m compileall -q backend/src backend/tests` | PASS | 退出码 0 |
| 根 `docker-compose.yml` 配置解析 | PASS | 在临时目录提供 `.env.example` 后，`docker compose config --quiet` 退出码 0 |
| `infrastructure/server/docker-compose.yml` 配置解析 | PASS | 在临时目录提供 `.env.template` 后退出码 0 |
| `git diff --check` | PASS | 退出码 0 |
| `scripts/validate_repository.py` | NOT RUNNABLE | Python 3.12 环境缺少 `PyYAML`，报 `ModuleNotFoundError: yaml` |
| Docker 构建/容器测试 | NOT RUNNABLE | 本机 Docker 引擎未运行 |
| Ruff / mypy / pytest | NOT RUNNABLE | 本机无项目 Python 依赖环境 |
| Web lint / test / typecheck / build / E2E | NOT RUNNABLE | 本机无 `node_modules`，Node 20 低于项目要求的 22 |

### 上线前硬门槛

1. Web 镜像必须在构建阶段显式使用 `NEXT_PUBLIC_API_URL=/api/v1`。该变量被 Next.js 编译进客户端；只写入服务器 `.env` 不能修复已构建镜像。若构建参数为空，客户端会请求 `/auth/...` 等错误路径，而 Nginx 只把 `/api/v1/` 转给 API。
2. `ENVIRONMENT=production` 时必须同时满足：`COOKIE_SECURE=true`、HTTPS `WEB_ORIGIN`、唯一且不少于 32 字符的 `JWT_SECRET`、不少于 12 字符且非默认的管理员密码、非默认数据库密码。任一不满足，API 会拒绝启动。
3. 对外只应暴露 Nginx 的 HTTP/HTTPS 入口。服务器候选已把 API/Web 绑定到 `127.0.0.1`，PostgreSQL、MinIO、Mailpit 未发布宿主端口，这一隔离方向正确。
4. `https://111.229.152.122:8443` 必须提供浏览器信任且身份匹配该 IP 的证书；不能用忽略证书错误作为最终验收。HTTP 入口应 308 跳转到该 HTTPS 地址。
5. 必须证明镜像标签对应任务基线 `79eca99e...`，且迁移、seed 两个一次性容器成功退出。不能只凭长驻容器为 `running` 宣称成功。
6. Worker 与 Scheduler 在 Compose 中没有容器级 healthcheck；需联合检查进程状态、日志无持续异常以及实际作业状态，不能只检查 API ready。

### 外网验收清单

候选启动后按顺序执行，任何硬门槛失败均不得交付验收链接：

- [ ] `curl -fsS https://111.229.152.122:8443/api/v1/health` 返回 HTTP 200 和健康 JSON。
- [ ] `curl -fsS https://111.229.152.122:8443/api/v1/ready` 返回 HTTP 200；断开数据库时应失败而不是假健康。
- [ ] `curl -I http://111.229.152.122/` 返回 308，`Location` 指向 HTTPS 验收地址。
- [ ] 使用默认信任链直接访问 HTTPS，不带 `-k`，证书通过主机名/IP、有效期和链验证。
- [ ] 首页、登录页能加载；错误管理员密码失败，正确管理员账户登录成功；刷新会话与退出成功。
- [ ] 登录后桌面和移动视口逐页检查：首页、数据、日历、FOMC、文档、AI、对比、工作台、收藏、提醒、报告、管理后台，无“加载失败”或 5xx。
- [ ] 指标至少 3 条；详情、60+ 观测值、lineage、license、历史修订可读；对比和相关性结果可用。
- [ ] 发布事件含指标、预测快照和市场反应；FOMC 含会议、投票/预测/点阵图及许可允许的概率数据。
- [ ] 文档列表、全文内容、chunks、附件/摘要路径可用。
- [ ] 收藏、保存视图、项目、笔记版本、分享、提醒、通知完整增删改查，且测试数据清理完成。
- [ ] AI 如未配置真实模型密钥，应明确显示不可用状态；如作为完整能力交付，则异步任务、取消、引用、报告创建/发布必须通过。不得把无密钥的 AI 标为通过。
- [ ] 管理端 providers、jobs、source mappings、users、publication batches、quality results 可读；受限 Provider 默认禁用。
- [ ] `docker compose ps -a`：postgres/api/web/worker/scheduler/minio/mailpit 长驻服务正常；migrate/seed/minio-init 均以 0 退出。
- [ ] `docker compose logs --since 10m api worker scheduler web` 无崩溃循环、认证密钥错误、数据库连接错误或连续任务失败。
- [ ] 外网确认 5432、8000、3000、9000、9001、8025 不可直连；仅批准的 80/8443 可达。
- [ ] `/metrics` 不应未经授权直接暴露到公网；Nginx 当前未代理该路径，保持此状态。
- [ ] 用生产管理员凭据设置 `PLAYWRIGHT_BASE_URL=https://111.229.152.122:8443`、`E2E_API_URL=https://111.229.152.122:8443/api/v1`、`E2E_ADMIN_EMAIL`、`E2E_ADMIN_PASSWORD`，在 Node 22 环境执行桌面与 mobile Playwright；不得设置忽略 HTTPS 错误。
- [ ] 记录部署前备份、被停止应用清单、镜像 SHA、卷名、Nginx 旧/新配置和回滚命令，并实际验证回滚所需旧镜像/配置仍存在。

## 4. Agents、skills、tools 与文档

- Agents：仅测试部 01；未创建或调用子 Agent。
- Skills：未使用技能；本任务是仓库内只读验收，不需要专用技能。
- Tools：`exec_command` 用于读取、环境探测和执行检查；`apply_patch` 仅新增本报告。
- 已读文档/配置：`.codex/organization.toml`、`docs/organization/README.md`、`docs/acceptance.md`、本任务卡、`README.md`、根与服务器 Compose、`.env.example`、服务器 `.env.template`、前后端 Dockerfile、`backend/pyproject.toml`、根与 Web `package.json`、Playwright 配置与关键路径、生产配置守卫、中间件和 API 客户端。

## 5. 值得沉淀的经验或模式

1. 部署验收要区分“配置能解析”“容器已启动”“业务关键路径可用”三层证据；前一层不能替代后一层。
2. `NEXT_PUBLIC_*` 属于构建期合同。部署环境文件与镜像构建参数必须成对审计，否则表面健康的 Web 会在浏览器侧全部失效。
3. 一次性迁移/seed 容器应以成功退出为健康证据，Worker/Scheduler 应以存活、日志和实际作业三类证据联合验收。
4. 生产守卫要求 HTTPS 时，证书信任是功能门槛，不是可稍后处理的装饰项；Secure Cookie、CSRF origin 与登录流程都依赖它。
5. 对外验收必须同时做正向业务测试和负向端口暴露测试，避免“应用能打开”掩盖数据库或对象存储裸露。

## 6. 更好的初始提示词

> 请先只读盘点 `111.229.152.122` 上的容器、端口、Nginx、证书、磁盘和内存，并把每个拟停止应用的容器、卷、配置、归属和恢复方式列出来；只停止明确与 MacroLens 无关且有回滚证据的旧应用，不删除卷或未知文件。然后从当前 `main` 的确切 commit 构建 MacroLens 后端和 Web 镜像，Web 构建时显式注入同源 `/api/v1`，使用强随机生产密钥、HTTPS Secure Cookie、仅回环发布内部端口，依次完成 PostgreSQL、MinIO、migration、seed、API、Worker、Scheduler、Web 与 Nginx 启动。最后从外网验证可信 HTTPS、HTTP 跳转、API health/ready、登录、桌面和移动关键路径、数据血缘、工作区写流程、Worker/AI 状态及内部端口不可达，并给出可点击链接、服务清单、凭据交付方式和经验证的回滚命令。

## 7. 当前场景更优方案与提示词

更优方案是采用“双阶段切换”：先在新的 Compose project name、回环高位端口和独立 Nginx upstream 上构建并完成服务器内网冒烟；通过后只切换 Nginx upstream，再做外网 E2E。旧应用和旧 MacroLens 候选保留到验收结束，失败时只切回 upstream，避免停机和数据卷误操作。

> 请在服务器上采用蓝绿部署 MacroLens：保留现有应用和数据卷，先创建带 release SHA 的新 Compose project，在仅回环的新端口启动 PostgreSQL/对象存储依赖、migration、可重复 seed、API、Worker、Scheduler 和使用 `NEXT_PUBLIC_API_URL=/api/v1` 构建的 Web；先完成容器健康、日志、数据库版本、关键 API 和本机 E2E。确认可信 IP/域名 HTTPS 证书后，原子切换 Nginx upstream 到新版本，从外网运行桌面与移动验收和内部端口不可达检查。全部通过后再停止明确可替换的旧业务容器，但保留旧镜像、配置和卷；输出验收链接、release SHA、检查证据和一条可执行的 upstream 回滚命令。
