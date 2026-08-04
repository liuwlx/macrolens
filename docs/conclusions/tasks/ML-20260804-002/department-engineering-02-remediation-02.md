# ML-20260804-002-R2 Engineering-02 修复报告

## 1. 问题与场景

首次启动创建了空 `.venv`。原脚本直接执行 `import asyncpg, psycopg, uvicorn` 判断依赖是否存在；缺模块会向 stderr 输出 traceback，而 Windows PowerShell 在全局 `ErrorActionPreference=Stop` 下把 native stderr 转成终止错误，脚本来不及读取退出码并进入 pip 安装分支。

## 2. 分析过程

缺依赖是预期分支，解释器损坏、命令语法错误或其他退出状态则必须失败。全局放宽错误策略会削弱 SSH、pip 和其他外部命令的 fail-closed 门禁。因此将模块检查放进 Python 进程内部：缺模块只返回约定退出码 3，不输出 traceback；PowerShell 仅在这一条 native 调用周围临时使用 Continue，并在 finally 中恢复原策略。

## 3. 解决流程

1. 新增 `Test-PythonRuntimeDependencies`，通过 `importlib.util.find_spec` 检测三个运行依赖。
2. 退出码 0 表示依赖齐全，3 表示缺模块；其他退出码一律抛错。
3. 新增 `Ensure-PythonRuntimeDependencies`，仅在退出码 3 时执行 `pip install -e backend`。
4. 隔离测试使用临时 `.cmd` 模拟缺模块和带 stderr 的非预期失败，验证前者恰好进入一次安装分支、后者不安装且失败，并验证 EAP 恢复为 Stop。

## 4. Agents、skills、tools 与文档

- Agents：主线程 `/root` 提供真实运行故障和 R2 任务卡；部门线程 `/root/engineering_02` 完成修复。
- Skills：未调用额外 skill。
- Tools：`apply_patch` 修改脚本、测试和报告；PowerShell/`exec_command` 执行解析、隔离行为测试、Pester 和 Git 检查；协作消息同步结果。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`，以及现有远程开发脚本和测试。

## 5. 可沉淀经验

Windows PowerShell 5.1 的 native stderr 不是普通文本流，在 Stop 策略下可能先于退出码判断终止流程。预期的 native 失败应使用专用退出码表示，并把错误策略放宽限制在最小 try/finally 作用域；未知退出码仍必须失败。

## 6. 更好的初始提示词

请修复 PowerShell 5.1 脚本首次空 `.venv` 时依赖探测无法进入安装分支的问题。不要直接运行会因 ModuleNotFoundError 写 stderr 的 import 命令；用 Python 内部无 traceback 的专用退出码区分“缺依赖”和“解释器异常”，仅局部临时调整 ErrorActionPreference 并 finally 恢复。增加隔离模拟测试，禁止访问远端。

## 7. 更优方案反思与提示词

更优的长期方案是把本地环境准备独立成显式 `Bootstrap` 动作，并用锁文件哈希作为依赖安装是否需要重跑的依据；Start 只做轻量、无副作用的运行前检查。这能缩短启动路径并使依赖失败更容易定位。

更优提示词：请将 PowerShell 远程开发工具拆成 Bootstrap 与 Start 两阶段；Bootstrap 原子创建 Python 3.12 venv 并按 backend 锁文件安装依赖，Start 只校验解释器、锁文件标记和模块可导入。所有 native 命令按退出码分类，局部处理预期失败，其他错误 fail closed，并提供离线模拟测试。
