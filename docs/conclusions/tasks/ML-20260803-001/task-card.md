# Task Card: ML-20260803-001

## Registration

- Source main task: `ML | 项目统筹部 | 主线程 | 01`
- Source thread ID: `019fc3a3-d0a0-7f13-b660-2010e36c7138`
- Task type: organization governance / agent instructions / documentation / validation
- Status: `RUNNING`
- Implementation commit: `d1e5b40804805e67681893af63cffd83fd0000e5`
- Remediation commit: `c9353fd1ed639bd84f0668dd57c50283435b65f7`
- Remediation-02 commit: `6a0b5b6d71b95140eaf1da524ba59befb63c20cd`
- Remediation-03 commit: `c1bcdac55a7b0238fbea0d3cafe391c0bf22bf64`
- Remediation-04 commit: `3c343b44a063f780afc16adccb96eb92758d3076`
- Remediation-05 commit: `12766ea0f6bb1ae967b0c98525025bef4dace60a`
- Remediation-06 commit: `bac5d0883d59d8ff7244e34a89631a3b05d7478a`
- Remediation-07 commit: `b05bfac2344d0816ecb2a85dfa38976e3096a0a6`
- Blocked integration report commit: `1c0c19412bd5c6b07b25f49f3e3a960da215a040`
- Blocked reintegration report commit: `7bdf1e6bc971774c96fd120a07801b5756698823`
- Blocked reintegration-03 report commit: `6e4f38d6d8acce4352c31504c3c6403dad7c2d67`
- Blocked reintegration-04 report commit: `dea54263eb20d790363ad1996bb1d84d9d91ad9d`
- Blocked reintegration-05 report commit: `7879ca714d8e88e89eea35216c0c0e3c18da1335`
- Blocked reintegration-06 report commit: `611c3eaeed72ebc01b6ca45b7b478ba3254a23a2`
- Blocked reintegration-07 report commit: `67be39069b71141798117ee3acb01644994769cf`
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
| SUPPORTING | `ML｜研发部｜席位｜04` | `019fc533-0419-7103-a9e4-173a356b0b67` | Implement approved rules and validator in an isolated worktree | `department-engineering-04.md` | PENDING | PENDING |
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

Reintegration review `dea54263` found one remaining lifecycle defect after 5 positive and 46 negative tests passed: an integration assignment could validate while `RUNNING` using its report commit, but no task-card field and validator path allowed the source main task to record the real integration commit before changing that department result to `SUCCEEDED`. The next remediation must make this transition explicit and fail closed when either the integration commit or integration report commit is absent.

Reintegration review `7879ca71` found three final-close defects after 9 positive and 51 negative tests passed: integration success did not force the task into `REVIEW` before final summary; final-summary Git checks incorrectly required original worktree candidate SHAs to be ancestors even though the approved workflow cherry-picks them to new main SHAs; and report fallback was broad enough to let some already-`SUCCEEDED` non-integration departments bypass explicit execution mappings. The next remediation must use real cherry-pick topology tests and distinguish source candidate SHAs from integrated main SHAs.

Reintegration review `611c3eae` showed that the source main task had prematurely marked Engineering `SUCCEEDED` before source-to-integrated mappings existed; until integration completes, that assignment must remain `RUNNING` and use the allowed report fallback. It also found that the validator did not enforce the reverse rule that source candidate commits must not be final-summary ancestors, and that the synthetic tests removed the real multi-department task directory instead of exercising the current topology.

Before redispatching integration, a source-main preflight of the next required Quality assignment found a close-path gap: a new v2 local, report-only department cannot legitimately supply a non-main source candidate commit. The contract therefore needs a narrowly scoped `LOCAL_REPORT` success path whose active receipt strictly precedes the report commit on main, while Engineering, Integration and any assignment that declares code commits continue to require source-to-integrated mapping.

Reintegration review `67be3906` found one remaining test-fixture defect after the candidate declared 13 positive and 83 negative tests: the real multi-department topology positive test mutates a floating clone by searching for `Integration=BLOCKED`, so it fails before validator execution when the target main correctly contains `Integration=RUNNING`. The remediation must make fixture state construction explicit and idempotent, then prove the full 96-test suite passes against the current RUNNING topology.

## Required checks

```powershell
python -X utf8 scripts/validate_organization.py
python -X utf8 scripts/validate_repository.py
git diff --check
```

## Reporting contract

Every department report and the main summary must identify the task ID, thread title/ID, actual scope, artifacts or commits, checks, evidence, risks/blockers, final status, and the seven conclusion sections required by the repository-level `AGENTS.md`.
