# Recommendation backlog

Status labels: `PRODUCTION`, `IMPLEMENTED BUT NOT DEPLOYED`, `PLANNED`, `DEFERRED`.

## Implemented but not deployed

- Discover v1 taste snapshot, canonical taxonomy, bounded multi-source retrieval, score decomposition, core/adjacent/discovery selection, deterministic diversity and adaptive 70/30 mix.
- Swipe retry idempotency marker and media-typed user/catalog identity migrations.
- Safe metadata backfill script (`backend/scripts/backfill_metadata.py`), default dry-run, bounded concurrency/rate and non-empty merge.
- Deterministic existing-user taste bootstrap (`backend/scripts/bootstrap_taste_profiles.py`), default dry-run, restartable slices and snapshot replacement.

## Planned before or during rollout

- Verify migrations against a disposable local/staging Supabase database, including composite foreign keys and existing rows.
- Run recommendation smoke/performance checks for cold cache, strict filters, sparse pool and upstream failure.
- Decide deployment order: migrations → backend → backfill → smoke test; retain rollback/backup plan.
- Add distributed cache/lock or move recommendation pool/session state out of process-local memory if backend scales horizontally.
- Add recommendation feedback analytics and offline quality evaluation.
- Run the controlled reset only after confirming which user-state tables are test-only;
  never delete `users` or catalog metadata.
- Add a multi-instance idempotency primitive if the backend is scaled horizontally;
  current row marker is safe for sequential frontend retries.

## Deferred

- TMDB keyword retrieval endpoint (local keyword metadata avoids N+1 and is sufficient for v1).
- Separate media-type ML model, random exploration, large event log, and full franchise/semantic-cluster graph.
- Automatic cleanup/retention job for old swipe idempotency markers if the marker is extended beyond the current row-level approach.
