# ML-20260804-002-R3 Engineering-02 修复报告

## 1. 问题与场景

PowerShell 5.1 在全局 `ErrorActionPreference=Stop` 下，会把 native stderr 转成终止错误。通用 `Invoke-Checked` 因此在读取 `$LASTEXITCODE` 前退出：pip 的完整错误被截断为 `ERROR: Exception:`，其他外部工具也存在相同风险。

## 2. 分析过程

R2 只收紧了依赖探测自身，未覆盖通用 native 执行边界。正确语义应是：native 命令可自由写 stdout/stderr，是否成功完全由退出码决定；PowerShell 错误策略只能在调用周围临时放宽，并必须恢复。失败输出可能含 URL 凭据或环境值，通用异常不得回显。pip 需要可操作诊断，但可通过固定类别而不是原始文本提供。

## 3. 解决流程

1. `Invoke-Checked` 在 try/finally 内局部使用 Continue，捕获合并输出和真实退出码，再恢复 EAP。
2. 成功时返回原合并输出；失败仅报告可执行文件名和退出码，不包含捕获内容。
3. 新增 pip 专用执行器，参数加入 60 秒超时、5 次重试和无交互；失败输出只映射为 network、disk-space、filesystem-permission、dependency-resolution、package-unavailable、build 或 unclassified。
4. 隔离 fake cmd 覆盖 stderr+exit 0、敏感 canary+exit 7、EAP 恢复和 pip 非秘密类别。

## 4. Agents、skills、tools 与文档

- Agents：主线程 `/root` 提供真实失败和 R3 任务卡；部门线程 `/root/engineering_02` 实施修复。
- Skills：修复前诊断阶段使用 `diagnosing-bugs` 建立受限 dry-run 反馈环；本次编码未调用额外 skill。
- Tools：`apply_patch` 修改脚本、测试和报告；PowerShell/`exec_command` 执行静态、隔离行为、Pester 与 Git 检查；协作消息同步结果。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、现有远程开发脚本和测试。

## 5. 可沉淀经验

PowerShell 调用 native 程序时，stderr 不是成功判据，退出码才是。统一边界应捕获输出、保存退出码、恢复错误策略，再决定成功或失败。敏感自动化中的错误输出应先分类或净化，默认不回显原文。

## 6. 更好的初始提示词

请修复 PowerShell 5.1 的 native 命令包装器：在全局 EAP Stop 下仍完整捕获 stdout/stderr 和真实退出码，finally 恢复 EAP；成功返回输出，失败默认只报告 exe 与退出码，不泄露输出。pip 使用独立受控错误分类，并设置有限 timeout/retries/no-input。用 fake cmd 的 stderr+exit0 和敏感 canary+exit7 做隔离回归测试。

## 7. 更优方案反思与提示词

长期更优方案是以 `System.Diagnostics.Process` 统一启动外部进程，分别异步读取 stdout/stderr、支持取消和超时，避免 PowerShell native 错误流语义。但对当前 PS5.1 脚本而言，局部 EAP 包装更小、更易审计。

更优提示词：请设计一个 PowerShell 5.1 `System.Diagnostics.Process` 执行模块，支持参数安全传递、stdin、stdout/stderr 分离、超时、取消、退出码和敏感输出策略；用 fake executable 覆盖大输出、stderr+exit0、超时、非零退出及 secret canary，并逐步替换现有 native 调用边界。
