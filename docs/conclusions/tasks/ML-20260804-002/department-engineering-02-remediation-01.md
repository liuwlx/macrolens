# ML-20260804-002-R1 Engineering-02 修复报告

## 1. 问题与场景

Windows PowerShell 5.1 通过 OpenSSH 执行远端 `docker inspect` 时，Go template 内用于索引 `macrolens_default` 的双引号在多层参数解析中丢失。Docker 将网络名误判成模板函数，导致 Provision 在任何 SQL 执行前失败。

## 2. 分析过程

真实运行错误为 `template: :1: function "macrolens_default" not defined`。原命令同时经过 PowerShell 参数组装、本地 OpenSSH 和远端 shell，内层双引号无法可靠保留。该场景不需要按名字在模板内索引网络；让模板遍历全部网络并输出无引号的 `name=ip` 行，再在本地严格筛选，能消除脆弱的嵌套引用。

## 3. 解决流程

1. 将 inspect template 改为遍历 `.NetworkSettings.Networks`，输出 `networkName=IPAddress`。
2. 新增 `Get-MacrolensNetworkIp`，只接受唯一的 `macrolens_default` 行和规范 IPv4；缺失、重复、IPv6、非法或非规范地址均失败。
3. 静态测试禁止恢复 `index .NetworkSettings.Networks` 和模板内层双引号，并覆盖有效、重复、非法 IP。
4. 新增真实 SSH 只读发现测试，仅调用 `Get-RemotePostgres`，不执行 SQL 或 Provision。

## 4. Agents、skills、tools 与文档

- Agents：主线程 `/root` 提供真实故障证据与修复任务卡；部门线程 `/root/engineering_02` 完成修复和验证。
- Skills：本修复未调用额外 skill。
- Tools：`apply_patch` 修改脚本、测试和报告；PowerShell/`exec_command` 执行解析、静态、Pester、Git 检查和真实 SSH 只读验证；协作消息向主线程回报。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`，以及现有 `scripts/remote-dev.ps1` 和测试。

## 5. 可沉淀经验

跨 PowerShell、OpenSSH、远端 shell 的命令应避免依赖嵌套引号。结构化数据可以使用无歧义的逐行键值输出，在可信本地代码中做唯一性与类型校验。真实只读集成测试应直接复用生产发现函数，避免测试命令与实现再次分叉。

## 6. 更好的初始提示词

请修复 Windows PowerShell 5.1 经 OpenSSH 调用远端 `docker inspect` 时 Go template 内层双引号丢失的问题。不要在模板中按带引号的网络名做 index；遍历网络输出 `name=IPv4`，本地只接受唯一 `macrolens_default` 的规范 IPv4。添加静态、边界和真实 SSH 只读测试，但不得执行 SQL、Provision、Start 或 Deprovision。

## 7. 更优方案反思与提示词

更优的长期方案是让远端返回 Docker JSON，并用本地 JSON 解析器读取 `NetworkSettings.Networks.macrolens_default.IPAddress`，彻底减少模板语言与 shell 的组合；但输出体积更大，当前逐行键值方案更小且已严格验证。

更优提示词：请比较“完整 Docker JSON 本地解析”和“无引号 name=ip 模板输出”两种跨 OpenSSH 方案，以 PowerShell 5.1 参数安全、输出大小、唯一性校验和可测试性为准选择方案；实现后用真实 SSH 只读测试验证，任何失败都不得触发 SQL。
