# MacroLens Engineering Rules

## Multi-thread coordination

- All MacroLens department threads must read `.codex/organization.toml` and
  `docs/organization/README.md` before accepting work.
- A numbered department seat may own only one active task at a time. Work requires a task card
  containing a task ID, source main thread, scope, success criteria, dependencies and checks.
- Main threads are peers. Each main thread owns only the user task assigned to it and must not
  take over or reprioritize another main thread's work.
- Code changes run in isolated Git worktrees. Department threads commit their changes; only the
  Integration and Release department integrates completed work into the baseline branch.
- Initialization-only turns that merely load the organization rules and remain idle do not need a
  separate conclusion report. Every substantive task still follows the report requirements above.

## Architecture

- Keep a modular monolith. Web, API and Worker are separate deployable processes, not separate business repositories.
- API business domains: catalog, observations, releases, FOMC, documents, AI, workspace, alerts and licensing.
- Provider-specific parsing stays in `macrolens_worker.providers`.
- Never call an official data provider directly from the browser.

## Non-negotiable data rules

1. Never overwrite an old observation vintage. Insert a new vintage and update `observation_latest` transactionally.
2. Every production observation must link to `source_series`, `ingestion_run` and preferably `raw_object`.
3. Derived series require a versioned formula and explicit dependencies.
4. Forecasts are time-varying snapshots; never keep only one mutable consensus value.
5. Licensing policy gates display, download, API redistribution and AI use.
6. AI outputs must preserve `data_as_of`, model, prompt version, context snapshots and citations.

## Security

- Secrets only come from environment variables or a secret manager.
- Authentication cookies are HttpOnly; production cookies are Secure.
- Enforce workspace ownership in every user-data query.
- Validate all file types and size limits before object-storage upload.
- Do not render untrusted HTML.

## Coding

- Python: Python 3.12+, type hints, Pydantic v2, SQLAlchemy 2 async style.
- TypeScript: strict mode, no `any` without a documented reason.
- API errors use RFC 9457-style problem details.
- All mutation endpoints must be idempotent where retry is plausible.
- Add tests for changes to transforms, vintage handling, authorization and provider normalization.

## Required checks

```bash
ruff check backend
mypy backend/src
pytest backend/tests
npm --workspace apps/web run lint
npm --workspace apps/web run test
npm --workspace apps/web run build
```
