# ML-20260815-007｜CI Alembic 导入路径修复报告

## 1. 问题与场景

PR #11 的 GitHub backend CI 在 Alembic round-trip 步骤失败。失败发生在连接临时 PostgreSQL 之前：工作流进入 `backend/` 后直接执行 `alembic`，但未把 `backend/src` 加入 Python 导入路径，`alembic/env.py` 因而无法导入 `macrolens_api`。本轮只修复远程 CI 的源码导入路径；本机没有启动 Docker、数据库或执行 Alembic，目标服务器也没有执行 migration、seed 或同步。

## 2. 分析过程

失败日志的精确信号是 `ModuleNotFoundError: No module named 'macrolens_api'`，栈停在 `backend/alembic/env.py` 第一次项目包导入处。按 `diagnosing-bugs` skill 排序并检验假设：第一，CI Alembic 步骤缺少 `PYTHONPATH=src`；第二，workflow 只安装 requirements 而未安装项目包；第三，`env.py` 没有自行修改 `sys.path`；第四，数据库或迁移错误。导入阶段已直接证伪第四项。正确边界是修正 workflow 运行环境，而不是污染迁移运行时代码或在本机启动数据库。

## 3. 解决流程与验证结果

先为 `.github/workflows/ci.yml` 建立静态 RED：要求唯一 Alembic round-trip 步骤同时使用 `working-directory: backend` 和 `PYTHONPATH: src`。旧工作流不能满足。随后把原单行 `cd backend && alembic ...` 改为 GitHub Actions 原生 `working-directory`，并为该步骤设置 `PYTHONPATH: src`；迁移命令本身不变。

本地验证均未使用容器或数据库：

- `pytest backend/tests/test_static_invariants.py -q`：3 passed。
- `ruff check backend`：通过。
- `mypy backend/src`：70 个源文件无问题。
- `pytest backend/tests -q`：229 passed，5 warnings。
- Web lint：0 errors，2 个既有 warnings。
- Web test：11 files、35 tests passed。
- Web build：Next 16.2.12 编译、类型检查和 15 个页面生成通过。
- `git diff --check`：通过。

## 4. Agents、skills、tools 与文档

- Agents：研发部 02/03 接收修复与复核任务；因席位未在时限内形成提交，主线程在确认无并发写者后完成验证、报告和冻结。集成发布部只负责后续 PR。
- Skill：`diagnosing-bugs`，用于先建立 CI 导入失败的紧凑信号、排序可证伪假设，再限定最小修复 seam。
- Tools：GitHub CLI、PowerShell、Git、`apply_patch`、Python 3.12、pytest、ruff、mypy、Node 22、npm、Vitest、ESLint、Next build。
- 文档：`AGENTS.md`、组织配置/手册、开发宪法 README 与 01/02/03、ML-20260815-007 任务卡、GitHub backend 失败日志。
- 阶段：01 本地候选修复与冻结；02 PR 仍未合并。GitHub CI 的临时服务运行在远程 runner，不属于本地 Docker。

## 5. 值得沉淀的经验与模式

Alembic CLI 能否导入应用包必须由 CI 工作目录和导入路径共同定义；不能依赖开发机 editable install。工作流错误应在 workflow seam 修复，不能为了 CI 修改 `env.py` 的生产导入行为。静态 invariant 可以在不启动数据库的情况下提前捕获这类“命令尚未连接数据库就失败”的配置回归。

## 6. 更好的初始提示词

> GitHub backend CI 在 `cd backend && alembic upgrade head` 处报 `ModuleNotFoundError: macrolens_api`。请先确认失败发生在数据库连接前，写一个静态回归测试约束 Alembic 步骤的工作目录和 `PYTHONPATH`，再只修改 CI workflow；不要改迁移代码、不要在本地启动 Docker/数据库或执行 migration。完成六门禁后提交修复并重新触发 PR CI。

## 7. 当前场景的一次性更优方案提示词

> 在 ML-20260815-007 候选上读取 PR #11 backend 失败日志，用不连接数据库的静态测试复现 `backend/` 下 Alembic 缺少 `src` 导入路径。将 workflow 改为 `working-directory: backend` 且步骤级 `PYTHONPATH: src`，保持 upgrade→downgrade→upgrade 命令不变；运行静态测试、项目六门禁和 diff check，记录本地 Docker/migration/seed/sync 均为零，再推送同一 PR 等待完整远程 CI。
