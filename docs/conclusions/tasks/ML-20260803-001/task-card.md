# Task Card: ML-20260803-001

## Registration

- Source main task: `ML | 项目统筹部 | 主线程 | 01`
- Source thread ID: `019fc3a3-d0a0-7f13-b660-2010e36c7138`
- Task type: organization governance / agent instructions / documentation / validation
- Status: `DISPATCHING`
- Created: 2026-08-03 (Asia/Shanghai)

## Goal

Update MacroLens task-execution governance so every substantive task is assigned to the correct department before work begins, each participating department records its result, and the main task publishes a final summary backed by verifiable dispatch evidence.

## Scope

- Update `AGENTS.md`, `.codex/organization.toml`, and `docs/organization/README.md` together.
- Add a machine-checkable organization-contract validator.
- Define hard prerequisites, assignment receipts, routing, stop conditions, department reports, and main-task summaries.
- Use this task as the first end-to-end example of the new process.

## Success criteria

1. Every substantive task requires one primary department and zero or more supporting departments before substantive work starts.
2. A department may start only after returning an assignment receipt containing task ID, role, thread title/ID, accepted scope, and report path.
3. No matching or available department seat causes a `BLOCKED` result; the main task may not silently take over or fabricate evidence later.
4. Routing rules and mandatory cross-department triggers cover architecture, product, data, research, AI/docs, engineering, testing, security, operations, integration/release, and knowledge management.
5. Each department writes a per-task report; the main task writes a separate summary under `docs/conclusions/tasks/<task-id>/`.
6. Machine validation detects missing or inconsistent mandatory governance fields.
7. Existing repository organization checks remain green.

## Departments

| Role | Department seat | Thread ID | Accepted scope | Expected report | Receipt | Result |
| --- | --- | --- | --- | --- | --- | --- |
| PRIMARY | `ML | 架构部 | 01` | `019fc531-f5a2-7c91-ba58-7bfb4ca8ceeb` | Design governance rules and exact cross-file contract | `department-architecture-01.md` | PENDING | PENDING |
| SUPPORTING | `ML | 知识管理部 | 01` | `019fc533-c4bb-71a3-b963-d39218141521` | Review task-card/report schemas and evidence completeness | `department-knowledge-01.md` | PENDING | PENDING |
| SUPPORTING | `ML | 研发部 | 04` | `019fc533-0419-7103-a9e4-173a356b0b67` | Implement approved rules and validator in an isolated worktree | `department-engineering-04.md` | PENDING | PENDING |
| SUPPORTING | `ML | 测试部 | 01` | `019fc533-101f-7111-8ad3-1ac090a62da2` | Independently verify contract and regression checks | `department-quality-01.md` | PENDING | PENDING |
| SUPPORTING | `ML | 集成发布部 | 01` | `019fc533-b3a2-7be2-96ce-f4990bda6d6e` | Integrate the engineering commit and verify baseline consistency | `department-integration-release-01.md` | PENDING | PENDING |

## Dependencies and order

1. Architecture and Knowledge Management accept and complete design/review locally.
2. Engineering accepts only after the design evidence is committed, then implements in an isolated worktree.
3. Integration and Release accepts the resulting commit and integrates it into `main`.
4. Testing accepts only after integration and independently validates the baseline.
5. The source main task records all receipts/results and publishes `summary.md`.

## Required checks

```powershell
python -X utf8 scripts/validate_organization.py
python -X utf8 scripts/validate_repository.py
git diff --check
```

## Reporting contract

Every department report and the main summary must identify the task ID, thread title/ID, actual scope, artifacts or commits, checks, evidence, risks/blockers, final status, and the seven conclusion sections required by the repository-level `AGENTS.md`.

