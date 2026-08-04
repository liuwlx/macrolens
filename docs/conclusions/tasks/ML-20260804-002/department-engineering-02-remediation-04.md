# ML-20260804-002-R4 Engineering-02 修复报告

## 1. 问题与场景

真实 Start 在依赖安装完成后仍以 `python.exe exit 1` 退出。短生命周期诊断隧道显示 `psycopg.ProgrammingError` 且无 SQLSTATE，证明 SQL 尚未发送；同时专用角色最初缺少读取 `public.alembic_version` 的权限。

## 2. 分析过程

API 的同步 SQLAlchemy URL 使用 `postgresql+psycopg://` driver scheme，这是 SQLAlchemy 合法格式，但 `psycopg.connect()`/libpq 只接受 `postgresql://`。Alembic 探针直接复用了 SQLAlchemy URL，导致客户端 conninfo 解析失败。迁移头检查还需要对唯一元数据表进行 SELECT，该权限不应扩大到 public 其他对象。

## 3. 解决流程

1. 新增严格 scheme 转换函数，只接受 `postgresql+psycopg://`，仅替换为 `postgresql://`。
2. Alembic 探针通过短生命周期环境变量读取转换后的 URL，finally 立即删除；连接信息不输出，API 原 SQLAlchemy URL 不变。
3. Provision 显式授予 public schema USAGE 和 `public.alembic_version` SELECT；Deprovision 对称撤销。
4. 测试验证编码密码、主机、端口、库名和 query 均保持不变，异常 scheme 失败，并禁止 Alembic 表写授权。

## 4. Agents、skills、tools 与文档

- Agents：主线程 `/root` 协调真实运行验收；部门线程 `/root/engineering_02` 诊断并实施 R4。
- Skills：本轮未调用额外 skill；此前诊断使用 `diagnosing-bugs` 的最小反馈环方法。
- Tools：`apply_patch` 修改脚本、测试和报告；PowerShell/`exec_command` 执行静态、Pester 和 Git 检查；协作消息同步证据。
- 文档：`AGENTS.md`、项目组织规则、远程开发脚本及现有测试。

## 5. 可沉淀经验

SQLAlchemy driver URL 与底层 DBAPI/libpq URL 不是可互换格式。跨层探针应在调用边界执行最小、可验证的 scheme 适配，并保持凭据及其他连接参数不变。数据库健康检查所需权限应精确到元数据单表。

## 6. 更好的初始提示词

请检查 PowerShell 启动器中 SQLAlchemy URL 是否被直接传给 psycopg。为 Alembic 探针仅把 `postgresql+psycopg://` 转为 `postgresql://`，其他连接字符逐字保持且不得输出；Provision 只给专用角色增加 `public.alembic_version` SELECT，并添加 scheme 与只读授权回归测试。

## 7. 更优方案反思与提示词

更优方案是在配置模型中同时暴露 SQLAlchemy URL 和原生 libpq conninfo，由一个经过测试的凭据对象生成，避免各调用点自行改写字符串。

更优提示词：请设计一个不泄密的数据库连接配置模块，从同一结构化配置生成 async SQLAlchemy URL、sync SQLAlchemy URL 和原生 psycopg conninfo；为特殊字符、IPv6、query 参数和日志脱敏建立参数化测试，并逐步替换字符串 replace 调用。
