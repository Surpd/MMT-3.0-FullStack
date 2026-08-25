---
name: mmt-database-baseline
description: Capture and document the existing My Movie Tracker Supabase database baseline without changing production semantics. Use for schema snapshots, migrations baseline, RLS verification, indexes, constraints, foreign keys, triggers, database reproducibility, or bringing database state under version control.
---
# My Movie Tracker Database Baseline
The first goal is observability and reproducibility, not schema redesign.
Read:
- `docs/DATA_MODEL.md`
- `docs/INTEGRATIONS.md`
- `docs/TECH_DEBT.md`
- `docs/ROADMAP.md`
## Critical constraint
The repository audit could not verify:
- authoritative SQL schema;
- migrations;
- indexes;
- foreign keys;
- unique constraints;
- RLS;
- triggers/functions.
Do not invent these.
## Workflow
1. Inspect all database accesses in the repository.
2. Build a list of assumptions the application currently makes.
3. If authorized Supabase metadata/schema access is available, inspect actual state.
4. Compare actual state with code assumptions.
5. Capture the current state as a baseline suitable for version control.
6. Do not change production semantics while creating the baseline.
Where practical, capture:
- tables;
- columns/types/defaults;
- primary keys;
- foreign keys;
- unique constraints;
- indexes;
- RLS enablement;
- policies;
- functions;
- triggers.
## Special checks
Verify assumptions around:
- `users`;
- `profiles`;
- `user_stats`;
- `movies`;
- `user_movies`;
- uniqueness of `(user_id, movie_id)`;
- user ownership/isolation;
- movie relations.
## Safety
Do not:
- drop anything;
- rewrite production data;
- disable RLS;
- enable new policies blindly;
- execute destructive migrations;
- rotate database credentials.
If production state cannot be accessed, produce a precise list of unknowns and stop short of fabricated migration files.
## Output
Separate:
- verified database facts;
- code assumptions;
- discrepancies;
- security-relevant findings;
- proposed follow-up migrations.
A baseline must describe reality before trying to improve reality.
