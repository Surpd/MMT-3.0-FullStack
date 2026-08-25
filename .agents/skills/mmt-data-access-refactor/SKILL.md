---
name: mmt-data-access-refactor
description: Safely consolidate My Movie Tracker Supabase data access. Use for duplicate Supabase clients, SupabaseDatabase versus DatabaseCRUD consolidation, direct db._client usage, repository or facade boundaries, duplicate database operations, or data-access testability improvements.
---
# My Movie Tracker Data Access Refactor
Do not begin by deleting the legacy layer.
Read:
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/TECH_DEBT.md`
## Characterize first
Before modifying architecture:
1. find every Supabase client construction;
2. find every call through `SupabaseDatabase`;
3. find every call through `DatabaseCRUD`;
4. find every direct `_client` access;
5. map operations by table;
6. identify duplicate implementations;
7. identify behavior differences;
8. add tests around behavior that could regress.
## Refactor strategy
Move toward one explicit application-facing data-access boundary.
Do this incrementally.
A good sequence is:
1. move direct route-level accesses behind an existing or new bounded method;
2. eliminate exact duplicate behavior;
3. migrate callers;
4. remove old methods only when no callers remain;
5. remove redundant client construction only after behavior is equivalent.
## Known audit findings
Pay special attention to:
- duplicate Supabase clients;
- `db._client` access from web routes;
- `DatabaseCRUD.save_movie` duplicate upsert;
- `users` versus legacy `profiles` behavior.
Do not collapse semantically different operations merely because their code looks similar.
## Database safety
Do not alter schema or production data as part of a code-layer refactor unless explicitly requested.
## Completion
Show:
- old call paths;
- new call paths;
- callers migrated;
- callers deliberately left untouched;
- tests proving behavior.
