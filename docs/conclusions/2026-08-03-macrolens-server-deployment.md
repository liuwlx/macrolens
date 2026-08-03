# MacroLens 服务器部署工作报告（2026-08-03）

## 1. 问题与场景

用户要求使用 `ubuntu` 账号，关闭服务器 `111.229.152.122` 上多余的应用，将当前 MacroLens 项目部署到该服务器，并交付一个可完整验收的公网链接。

本次工作的主要约束如下：

- 服务器上已有多套 `tuntun-*` Docker 应用和多份 Nginx 配置，不能误停 SSH、Docker、Nginx、网络、防火墙等基础设施，也不能直接删除旧应用的数据、镜像和卷。
- 当前项目包含 Web、API、Worker、Scheduler、PostgreSQL/pgvector、MinIO 和 Mailpit 等多个进程，需要完成数据库迁移、种子数据、反向代理、TLS 和公网端到端验收。
- 服务器公网 `443` 不可用，但 `8443` 已开放；已有 Let's Encrypt IP 证书可以覆盖 `111.229.152.122`。
- 部分官方数据源需要 FRED、BLS、EIA API Key，而本次部署没有获得这些外部凭据。

## 2. 分析过程

1. 先读取组织规则和任务卡要求，确认由 Operations、Security、Engineering、Quality、Integration & Release 分工审阅。
2. 通过只读 SSH 盘点服务器系统、端口、Docker 容器、重启策略、Nginx 站点、证书、磁盘和内存，识别出旧应用均为 `tuntun-*`，基础设施服务需要保留。
3. 审查项目的 Dockerfile、Compose、环境变量、健康检查、前端 API 地址和 Nginx 路由，发现生产部署缺少服务器级编排文件，前端构建还存在一个 TypeScript 调用错误和 ECharts peer dependency 冲突。
4. 使用 `diagnosing-bugs` 技能追踪 Web 构建失败根因，修复 `mutate` 参数类型，并将 `echarts-for-react` 升级到兼容 ECharts 6 的版本。
5. 构建镜像时，Docker 构建网络访问 PyPI 不稳定；确认不是代码或依赖声明错误后，使用服务器已有代理和腾讯 PyPI 镜像完成可复现构建。
6. 首次登录验收发现种子管理员邮箱 `admin@macrolens.local` 不符合生产登录接口的严格邮箱校验；事务性调整为 `admin@macrolens.example.com`，并重新创建 API、Worker、Scheduler。
7. 运行日志检查发现 FRED、BLS、EIA 因缺少 API Key 产生后台失败任务。检查调度器代码后确认 `source.provider.active` 是正式启停开关，因此在种子初始化完成后暂停这三个数据源，并跨一个调度周期确认没有新增失败。
8. 证书续期复核发现系统包 Certbot 2.9 与签发 IP 证书的 Snap Certbot 5.7 并存，旧版定时器无法解析 IP 证书续期参数。停用旧版定时器，保留并验证 Snap 定时器，生产证书模拟续期成功，既有部署钩子会在续期后检查并 reload Nginx。

## 3. 解决流程与结果

### 代码与部署配置

- 部署代码版本：`8092075dc8cdf5d0e8a8a6ea9a202feec15949ad`（`deploy: prepare server release candidate`）。
- 新增服务器部署 Compose、生产环境变量示例和 Nginx 配置。
- 修复报告页生产构建类型错误。
- 修复 ECharts 6 的 React peer dependency 兼容性。
- 生产镜像：
  - Backend：`sha256:77a9f4fd22bb8147a18fa47051cff0ee44fdd56f231a76f4d2e2a0362697352a`
  - Web：`sha256:59b7eea6445dffd4da406b9ea0e3e18201d7ea67d4daee798af5484a7a897510`

### 服务器变更

- 使用账号：`ubuntu`，通过免密 `sudo` 执行受控运维命令。
- 停止并设置为不自动重启的旧应用容器共 10 个：`tuntun-agents-*`、`tuntun-platform-data-*`、`tuntun-order-*`、`tuntun-admin-*`。旧容器、镜像、卷和目录均未删除。
- 部署目录：`/opt/macrolens/releases/8092075dc8cdf5d0e8a8a6ea9a202feec15949ad`。
- 当前版本指针：`/opt/macrolens/current`。
- 真实生产环境变量：`/opt/macrolens/shared/.env`，权限为 `600`，未写入仓库或报告。
- 旧 Nginx 和 Docker 状态备份：`/opt/backups/macrolens-predeploy-20260803T1035Z`。
- 旧 Nginx 站点移动到：`/etc/nginx/disabled-macrolens-20260803T1117Z`。
- 部署初始数据库备份：`/opt/backups/macrolens-initial-8092075dc8cdf5d0e8a8a6ea9a202feec15949ad.sql.gz`。
- 部署最终数据库备份：`/opt/backups/macrolens-final-8092075dc8cdf5d0e8a8a6ea9a202feec15949ad.sql.gz`，SHA-256 为 `609fd1ee309ba2420a102d0b8004e385ee28fba6e87e7e732896ab036afc95d1`。
- 构建阶段临时代理已停止，端口 `17890` 不再监听。

### 运行状态和验收

- 公网验收链接：`https://111.229.152.122:8443/`。
- API 健康链接：`https://111.229.152.122:8443/api/v1/ready`。
- `http://111.229.152.122/` 返回 308 并跳转到 HTTPS 验收链接。
- Nginx 配置检查通过，唯一启用站点为 `macrolens`。
- API、Worker、Scheduler、PostgreSQL 均为 `healthy`；Web、MinIO 正常运行；迁移、种子和 MinIO 初始化任务均以退出码 0 完成。
- TLS 证书 SAN 精确包含 IP `111.229.152.122`，公网客户端在不开启不安全跳过校验的情况下通过验证；Snap Certbot 5.7 自动续期定时器为 `enabled/active`，生产证书 `renew --dry-run` 成功，续期后 Nginx reload 钩子已存在并可执行。
- 12 个主要页面均返回 200：登录、数据、日历、FOMC、文档、AI、对比、工作区、收藏、提醒、报告、管理后台。
- 登录、`/auth/me`、安全 Cookie、关闭公开注册、跨域 CSRF 拦截、退出登录均通过。
- MinIO 上传、预签名公网下载和内容一致性验证通过。
- 11 个关键 API 读取路径通过，包括分类树、序列、发布日历、FOMC、文档、AI、项目、收藏、提醒、报告和管理任务。
- FRED、BLS、EIA 三个需要外部 Key 的可选采集源暂时标记为非活动；Treasury、FOMC 等无需该三项凭据的链路保持运行。

### 回滚方式

1. 停止 `/opt/macrolens/current` 对应的 MacroLens Compose 栈。
2. 恢复 `/etc/nginx/disabled-macrolens-20260803T1117Z` 中的旧站点并执行 `nginx -t` 后 reload。
3. 将需要恢复的旧容器重启策略改回原值 `unless-stopped`，再按需启动旧容器。
4. 数据恢复可使用部署初始或最终 PostgreSQL 备份；对象数据保存在 `macrolens_minio_data` Docker 卷中。

## 4. Agents、Skills、Tools 与文档

### Agents

- 主 Agent `/root`：任务统筹、代码检查、服务器操作、部署、端到端验收和报告。
- `operations_01`（Lovelace）：服务器资产、运行服务、端口、容量和部署风险盘点。
- `security_01`（Singer）：SSH、TLS、密钥、端口暴露、Cookie、注册和 CSRF 安全审阅。
- `engineering_01`（Ptolemy）：生产 Compose/Nginx 配置与 Web 构建修复。
- `quality_01`（Bernoulli）：构建、静态检查、测试和验收矩阵。
- `integration_release_01`（Kuhn）：集成审阅、部署候选提交和发布前检查。

### Skills

- `diagnosing-bugs`：用于定位并修复 Web 生产构建失败，以及根据运行日志追踪可选数据源凭据错误。

### Tools

- `exec_command` / `write_stdin`：本地 Git、Node/Python/Compose 检查，以及经 SSH 执行远程 Docker、Nginx、OpenSSL、PostgreSQL 和公网验收命令。
- `apply_patch`：以可审阅补丁方式写入代码、部署配置和本报告。
- 多 Agent 协作工具：将独立的运维、安全、工程、质量和发布检查分配给对应部门席位。
- `curl`：验证公网 HTTPS、HTTP 跳转、页面、API、认证和对象存储。

### 阅读的文档与关键代码

- `.codex/organization.toml`
- `docs/organization/README.md`
- 根目录 `AGENTS.md` 中的项目规则
- `C:\Users\liuwl\.codex\skills\diagnosing-bugs\SKILL.md`
- 项目 README、Dockerfile、Compose、环境变量示例、Nginx 配置、数据库模型、种子命令、Worker runner、Scheduler 和 Provider adapters
- `docs/conclusions/tasks/ML-20260803-002/task-card.md`
- `docs/conclusions/tasks/ML-20260803-002/department-engineering-01.md`
- `docs/conclusions/tasks/ML-20260803-002/department-quality-01.md`
- `docs/conclusions/tasks/ML-20260803-002/department-integration-release-01.md`

## 5. 值得沉淀的经验与模式

1. 远程替换应用应先建立“保留清单”和“停止清单”，再逐个核对容器名、端口和重启策略；停止不等于删除，默认保留旧数据能显著降低回滚成本。
2. 部署验收不能只看首页，应覆盖浏览器路由、API 健康、身份认证、Cookie/CSRF、关键业务读取、对象存储、后台任务和跨调度周期日志。
3. 一次性迁移/种子容器可能在 `docker compose up <service>` 时被重新执行并覆盖运维状态；初始化完成后若只需恢复某个已存在容器，应使用精确 `docker start`，或把数据源启停策略做成显式部署配置。
4. 外部数据源凭据应在调度入队前进行 readiness gate；缺少凭据的 Provider 不应先排队再由 Worker 失败。
5. 生产依赖应尽量固定到镜像 digest。目前第三方镜像虽已记录实际 digest，但 Compose 仍使用 `latest`/宽泛标签，后续应固化。
6. IP HTTPS 可以作为短期验收方案，但正式长期环境更适合使用受控域名、标准 443 端口和监控告警。
7. 本次完整仓库检查还暴露了既有的 lint 报错和 Vitest ESM 兼容问题；它们不阻断已通过的生产构建和运行验收，但应单独建立治理任务。
8. 同机安装多个 Certbot 时，续期定时器必须与签发证书的版本一致；只检查证书当前有效还不够，必须验证实际 timer、执行文件、模拟续期和 deploy hook。

## 6. 更好的初始提示词

> 请使用 `ubuntu` 账号登录 `111.229.152.122`。先只读盘点服务器上的 Docker 容器、端口、Nginx、TLS、磁盘和内存，区分旧业务应用与 SSH/Docker/Nginx/网络等基础设施。备份旧配置后，停止并禁止旧业务容器自动重启，但不要删除容器、镜像、卷或数据。然后把当前 MacroLens 项目以生产方式部署到 `/opt/macrolens/releases/<git-sha>`，使用随机强密钥和仅服务器可读的环境文件，完成迁移、种子数据、Web/API/Worker/Scheduler/PostgreSQL/MinIO 健康检查，配置可信 HTTPS。最后从公网验证所有主要页面、登录与 Cookie/CSRF、关键 API、对象存储上传下载和后台调度，并给我验收链接、部署版本、备份路径、回滚方法和未配置的外部凭据清单。不要在回复中泄露密码。

## 7. 反思与更优方案提示词

当前方案在不获得域名和外部 API Key 的前提下已经完成可运行交付，但长期方案仍可优化：使用受控域名和标准 443，建立镜像仓库并固定 digest，把 Provider readiness gate 纳入调度器，把部署过程做成幂等脚本/CI 工作流，并为证书、容器健康、任务失败和备份恢复配置监控。

一次解决这些长期问题的更优提示词如下：

> 请把当前 MacroLens 部署为可长期维护的生产环境。目标服务器是 `ubuntu@111.229.152.122`；我会提供一个已解析到该 IP 的正式域名以及 FRED、BLS、EIA API Key。请先备份并可逆地停用旧业务应用，再修复所有阻断生产的构建和测试问题；构建带 Git SHA 的 Web/API 镜像并推送到私有镜像仓库，第三方镜像全部固定 digest。用幂等部署脚本或 CI 在 `/opt/macrolens/releases/<git-sha>` 发布，标准 443 提供 HTTPS，密钥只进入服务器 secret 文件。调度器必须在入队前检查 Provider 凭据，未就绪的数据源不产生失败任务。部署后执行数据库迁移、种子、备份与恢复演练，并从公网完成页面、认证安全、业务 API、对象存储、数据采集和跨调度周期的端到端验收；最后交付链接、版本、镜像 digest、监控状态、备份与一键回滚命令。
