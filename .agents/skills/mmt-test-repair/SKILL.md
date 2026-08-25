---
name: mmt-test-repair
description: Repair and stabilize the My Movie Tracker backend test environment. Use when pytest or backend tests fail because of imports, package layout, test discovery, config loading, root-directory execution, fixtures, or when adding regression coverage for audited behavior.
---
# My Movie Tracker Test Repair
Make the test suite runnable reliably from the repository root.
Read:
- `docs/TECH_DEBT.md`
- `docs/ROADMAP.md`
## Goals
The expected developer workflow should support one documented command from the repository root for backend tests.
Fix root causes rather than manipulating `PYTHONPATH` ad hoc in every test.
## Workflow
1. Reproduce the current failure.
2. Determine why imports such as `config` or `services` depend on working directory.
3. Inspect the existing package structure before changing imports.
4. Choose the smallest coherent packaging/import fix.
5. Avoid mass import rewrites unless required.
6. Re-run existing tests.
7. Add regression coverage only where valuable.
## Rules
Do not:
- delete failing tests;
- mark real failures as skipped without justification;
- catch import failures and pretend success;
- alter production behavior solely for test convenience.
Prefer explicit package imports and deterministic test setup.
## Validation
Run, as applicable:
- Python compile checks;
- backend unit/integration tests;
- frontend lint only if frontend code changed.
Report separately:
- infrastructure/test-runner failures;
- actual application-test failures.
