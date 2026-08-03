# Task Card: ML-20260803-001

## Registration

- Source main task: `ML | 项目统筹部 | 主线程 | 01`
- Source thread ID: `019fc3a3-d0a0-7f13-b660-2010e36c7138`
- Task type: organization governance / agent instructions / documentation / validation
- Status: `RUNNING`
- Implementation commit: `d1e5b40804805e67681893af63cffd83fd0000e5`
- Remediation commit: `c9353fd1ed639bd84f0668dd57c50283435b65f7`
- Remediation-02 commit: `6a0b5b6d71b95140eaf1da524ba59befb63c20cd`
- Blocked integration report commit: `1c0c19412bd5c6b07b25f49f3e3a960da215a040`
- Blocked reintegration report commit: `7bdf1e6bc971774c96fd120a07801b5756698823`
- Blocked reintegration-03 report commit: `6e4f38d6d8acce4352c31504c3c6403dad7c2d67`
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
| PRIMARY | `ML | 架构部 | 01` | `019fc531-f5a2-7c91-ba58-7bfb4ca8ceeb` | Design governance rules and exact cross-file contract | `department-architecture-01.md` | RESERVED | SUCCEEDED |
| SUPPORTING | `ML | 知识管理部 | 01` | `019fc533-c4bb-71a3-b963-d39218141521` | Review task-card/report schemas and evidence completeness | `department-knowledge-01.md` | RESERVED | SUCCEEDED |
| SUPPORTING | `ML｜研发部｜席位｜04` | `019fc533-0419-7103-a9e4-173a356b0b67` | Implement approved rules and validator in an isolated worktree | `department-engineering-04.md` | RESERVED | RUNNING |
| SUPPORTING | `ML | 测试部 | 01` | `019fc533-101f-7111-8ad3-1ac090a62da2` | Independently verify contract and regression checks | `department-quality-01.md` | PENDING | PENDING |
| SUPPORTING | `ML｜集成发布部｜席位｜01` | `019fc533-b3a2-7be2-96ce-f4990bda6d6e` | Integrate the engineering commit and verify baseline consistency | `department-integration-release-01.md` | RESERVED | BLOCKED |

## Dependencies and order

1. Architecture and Knowledge Management accept and complete design/review locally.
2. Engineering accepts only after the design evidence is committed, then implements in an isolated worktree.
3. Integration and Release accepts the resulting commit and integrates it into `main`.
4. Testing accepts only after integration and independently validates the baseline.
5. The source main task records all receipts/results and publishes `summary.md`.

## Active remediation

Integration review `1c0c194` blocked the first implementation for three concrete reasons:

1. The validator did not enforce all success and failure receipt fields.
2. Multi-word department report slugs were inconsistent with the report path template.
3. Several declared task-evidence gates were checked only as enabled flags rather than executed against task evidence, and negative tests did not cover those false negatives.

Reintegration review `7bdf1e6` confirmed the slug fix but found remaining blockers: status-specific raw receipt fields were still incomplete; task-card revisions and remediation receipts were not fully bound to Git history; report/summary identity checks were partial; only 15 negative tests existed; the direct test-file command failed; and the source main task had produced one malformed review receipt, now explicitly invalidated without altering its raw evidence.

Reintegration review `6e4f38d6` confirmed direct execution and 36 negative tests, but blocked the candidate again: a new receipt could omit `Evidence status` and downgrade to legacy; the complete ACTIVE/BLOCKED field rules conflicted; current receipt content was not bound before the matching implementation/remediation commit; v2 reports could remove their version to bypass identity checks; summary checks still omitted receipts, commits, integration evidence, and department-result details. It also rejected the task card's earlier ad-hoc status values, which this revision replaces with the contract state machine.

## Required checks

```powershell
python -X utf8 scripts/validate_organization.py
python -X utf8 scripts/validate_repository.py
git diff --check
```

## Reporting contract

Every department report and the main summary must identify the task ID, thread title/ID, actual scope, artifacts or commits, checks, evidence, risks/blockers, final status, and the seven conclusion sections required by the repository-level `AGENTS.md`.
