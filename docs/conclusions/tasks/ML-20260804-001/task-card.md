# Task Card: ML-20260804-001

## Registration

- Source main thread: `/root`
- Task type: full-stack data browser implementation and visual reconstruction
- Status: `REVIEW`
- Starting commit: `b5ab5ed3cb2eec553bba4c4bc878c3abec5d0da8`
- Created: 2026-08-04 (Asia/Shanghai)
- Source plan: `docs/conclusions/2026-08-04-data-overview-complete-implementation-plan.md`
- Structural source: `C:/Users/liuwl/AppData/Local/Temp/codex-clipboard-e70316c8-1620-4bf3-8862-d2309bf2517e.png`
- Visual source: `C:/Users/liuwl/AppData/Local/Temp/codex-clipboard-652b5f97-c231-41ad-85dd-b0fad92cfedc.png`

## Goal and business scenario

Rebuild `/data` as the confirmed MacroLens data browser: preserve the existing AppShell, render a lazy taxonomy tree, a metric summary table, a selected-series detail pane, and an analysis area spanning the table/detail columns. The core filters and actions must be backed by real APIs and remain subject to snapshot and licensing rules.

## Success criteria

1. At `>=1280px`, the page uses the confirmed three-column structure and the metric tree continues beside the lower analysis area.
2. The table supports filters, stable pagination and sorting with current, previous, change, period change and YoY values from one `data_as_of` snapshot.
3. Row selection drives detail, trend, history, revisions, documents, statistics and contribution availability without clearing other panes on a local failure.
4. Favorite, compare, export and AI-context actions work and enforce workspace and license rules.
5. Tablet/mobile layouts use drawers or a bottom sheet without blocking the core table flow.
6. Backend query paths avoid per-row latest-value/license N+1 queries and preserve all observation vintages.
7. Required repository checks, targeted tests, E2E, visual captures and `design-qa.md` pass before handoff.
8. A feature flag keeps the legacy page available for rollback.

## Scope in

- Browser/taxonomy/analytics/export/AI-capability read contracts and services.
- `/data` component rebuild, URL state, responsive behavior and cross-page actions.
- SDK/types, focused tests, E2E fixtures, design QA and release documentation.
- Minimal compare/AI changes required to accept selected series.

## Scope out

- No production flag switch or server deployment without a separate approval.
- No observation vintage overwrite, deletion, migration rewrite or data backfill.
- No arbitrary evaluation of `weight_expression`.
- No unrelated AppShell or other page redesign.

## Assignments

| Role | Seat | Scope | Worktree | Expected report | Status |
|---|---|---|---|---|---|
| PRIMARY | `engineering-01` | Backend contracts, batched services, tests and SDK API methods | `E:/workerspace/projects/20260709/macrolens-worktrees/ML-20260804-001-engineering-01` | `department-engineering-01.md` | COMPLETE |
| SUPPORTING | `engineering-02` | Frontend data browser, responsive UI, interactions and component tests | `E:/workerspace/projects/20260709/macrolens-worktrees/ML-20260804-001-engineering-02` | `department-engineering-02.md` | COMPLETE |
| SUPPORTING | `security-01` | License/snapshot/export/AI security review | local read-only, then integrated baseline | `department-security-01.md` | REVIEW / TOOL GATE |
| SUPPORTING | `quality-01` | Baseline capture, targeted/E2E/visual validation | integrated baseline | `department-quality-01.md` | FINAL REVIEW |
| SUPPORTING | `integration-release-01` | Cherry-pick candidates, resolve conflicts, run full gate | baseline `main` | `department-integration-release-01.md` | COMPLETE |
| SUPPORTING | `operations-01` | Local preview runtime and handoff check; no production switch | integrated baseline | `department-operations-01.md` | LOCAL PREVIEW |

## Public interface and Schema impact

- Adds `GET /taxonomies/{tree_code}/children`.
- Adds `GET /series/browser`, `/series/browser/export`, `/series/{id}/analytics`.
- Adds `GET /ai/capabilities?series_id=...`.
- Extends TypeScript web types and SDK methods without breaking current endpoints.
- API errors remain RFC 9457-style problem details.

## Dependencies and order

1. Backend and frontend may work in parallel from this frozen task card and implementation plan.
2. Backend candidate lands before frontend candidate so API/SDK contracts are authoritative.
3. Integration and Release cherry-picks both candidates and resolves only contract-level overlap.
4. Security and Quality validate the integrated baseline and return actionable findings.
5. Engineering remediation is assigned only for validated findings.
6. Operations starts a local preview only after build and targeted tests are green.

## Security amendments (2026-08-04)

These amendments override conflicting wording in the source plan:

1. `display_allowed` does not by itself authorize unauthenticated API redistribution. Browser and analytics value responses must be restricted to an authenticated in-product audience or require `api_redistribution_allowed` for a public audience.
2. Selected-series CSV export must use an authenticated server endpoint. The browser must not manufacture a downloadable CSV from a display-only observations response.
3. Every export must complete the full `download_allowed` preflight before writing response bytes. Any denied item fails the entire export.
4. `data_as_of` is a query cutoff over append-only `ObservationVintage` rows (`vintage_at <= cutoff`, latest version per period). `ObservationLatest` cannot be presented as a historical snapshot.
5. Zero verified primary sources and multiple verified primary sources are both fail-closed states; never select an arbitrary row with `.first()`.
6. Because `SeriesDependency` does not currently bind to a specific derived-definition version, contribution analysis is unavailable unless an unambiguous version relationship can be proven without schema guessing. Never evaluate arbitrary `weight_expression`.

## Remediation 01 (2026-08-04)

Quality review of integrated candidate `2e3484981c0696e960ec3b27cb78464454830b1c` found two release blockers:

1. `GET /series/{id}/observations` and `GET /series/{id}/revisions` must accept the same `data_as_of` cutoff used by browser and analytics, query `ObservationVintage` at that cutoff, and require `CurrentUser` plus `CurrentWorkspace`. They must never silently return latest values for a frozen page snapshot or expose numeric data anonymously.
2. `browser_series` must apply stable series ordering and pagination before loading observation histories. A 20-row page must not load up to 420 observations for every matching series. Facet counts may use the full filtered identifier set, while value computation is limited to the paginated identifiers.
3. If an AI run records a historical `data_as_of`, every attached context must be reproducible at that cutoff. Context types without a reliable version/effective-time boundary must fail closed instead of attaching current state to a historical run.
4. Validation failures for the new query contracts must be returned as RFC 9457-style problem details rather than FastAPI's default validation body.
5. Retried `POST /ai/runs` requests must be idempotent through the repository's existing mutation pattern or a minimal explicit idempotency key contract.

Engineering 01 owns remediation in a fresh isolated worktree based on integrated main. Security and Quality must re-review the resulting integrated candidate before runtime or visual acceptance resumes.

## Backend Remediation 02 (2026-08-04)

Focused review after Remediation 01 found two remaining P1 items:

1. The shared legacy primary-source resolver still used `.first()` and therefore selected an arbitrary mapping when more than one verified primary source existed. The integrated fix now returns not-ready for zero mappings, the unique tuple for one mapping and `409 source_mapping_conflict` for multiple mappings; observations and revisions share this behavior.
2. `current_period`, `current`, `change`, `period_change` and `yoy` were previously sorted after pagination. The integrated fix builds strict-license, `data_as_of`-bounded sort keys with a batched narrow-window query, applies stable global sorting before offset/limit, and loads the full 420-point history only for the selected page.

Integration evidence: 26 focused backend tests passed, including all five cross-page sort contracts, primary-source 0/1/>1 cases and PostgreSQL-dialect interval compilation.

## Web Remediation 02 (2026-08-04)

Browser acceptance at a 390px viewport found a remaining page-level horizontal overflow: the viewport was 390px wide while `document.documentElement.scrollWidth` reached 545px. The table wrapper correctly retained its own horizontal scrolling, but the 690px table/sticky-cell overflow still propagated to the root page.

Engineering 02 owns the smallest scoped correction in a fresh isolated worktree based on integrated main `79e65c07298e19e2d183300ec9ef9fad2bc4ce41`:

1. Stop horizontal overflow propagation at the data-browser page boundary without applying a global `body`/`html` overflow workaround.
2. Preserve horizontal scrolling inside `.data-browser-table-wrap` and `.data-browser-tabs`.
3. Add focused regression coverage for the page boundary and the two intentional internal scroll containers.
4. Re-run changed-path lint/typecheck/build/tests and browser acceptance at 390, 768, 1024 and 1280 pixels before release review.

## Required checks

```powershell
ruff check backend
mypy backend/src
pytest backend/tests
npm --workspace apps/web run lint
npm --workspace apps/web run test
npm --workspace apps/web run build
npm --workspace apps/web run typecheck
npm --workspace packages/sdk-typescript run typecheck
npm --workspace apps/web run e2e
git diff --check
```

## Expected deliverables

- Backend and frontend candidate commits.
- Integrated main-branch commit(s).
- Department reports under `docs/conclusions/tasks/ML-20260804-001/`.
- Root `design-qa.md` with `final result: passed`.
- Final conclusion report with the repository-required seven sections.

## Blocked return conditions

- Required visual source cannot be opened or implementation cannot be captured.
- A requested snapshot cannot be reproduced without silently using latest.
- License rules cannot be established without expanding scope or exposing data.
- An existing user change overlaps the required code and cannot be preserved safely.
- Required credentials or external deployment authority are missing; implementation and local verification should still continue.
