# Roadmap

## P0 — before further product work

| Task | Why / effect | Size | Dependencies |
|---|---|---|---|
| ~~Bind request user to validated Telegram identity~~ | completed: prevents cross-user reads/writes | S | auth regression tests |
| ~~Remove/contain production `DEV_MODE` bypass and hardcoded fallback~~ | completed: local-only bypass and explicit dev ID | S | auth regression tests |
| ~~Verify Supabase schema, foreign keys and RLS~~ | completed: production schema verified; RLS enabled and public table privileges revoked | M | Supabase access |
| ~~Validate rating, IDs, page/cursor and quiz answer~~ | completed: server-side validation and one-time quiz token | M | API regression tests |

## P1 — stability

- ~~Make swipe/rating writes observable and retryable~~; swipe has bounded retry and surfaced failure, rating remains awaited; M.
- ~~Configure deployed Mini App URL through env~~; production value still requires manual configuration; S.
- ~~Fix backend test invocation/package imports and add route/auth regression tests~~; root unittest command works; M.
- ~~Add structured recommendation timing logs for taste load, TMDB retrieval, metadata join, scoring, rerank and total request~~; implemented in `RecommendationService.get_next_movies`, deployment pending.

## P2 — architecture

- Consolidate `SupabaseDatabase`/`DatabaseCRUD` and stop direct `_client` use in handlers; L.
- Add versioned schema/migrations and policy automation for future changes; current RLS remediation is documented and applied; L.
- Replace process-local cache/FSM assumptions if running multiple workers; planned M/L. v1 has per-user in-process lock and bounded shown-ID state only.
- ~~Add bounded parallelism and deduplication around recommendation enrichment~~; implemented but not deployed: shared TMDB request budget and one local metadata join.

## P3 — product

- ~~Use explicit ratings as recommendation signal~~; bounded genre-affinity signal added; M.
- ~~Improve AI search with validated structured output and year matching~~; media-type/product personalization remain unchanged; M.
- Complete TV seasons/episodes only if product scope needs it; L.
- Add recommendation feedback analytics and quality evaluation; M/L.

## Discover Recommendations v1 status

- `IMPLEMENTED BUT NOT DEPLOYED`: normalized EMA taste profile, deterministic existing-user bootstrap, canonical genre source, media identity/idempotency code, controlled retrieval, core/adjacent/discovery buckets, scoring decomposition, diversity, adaptive mix, reasons and metadata backfill tooling.
- `PLANNED`: disposable staging migration verification, production rollout, backfill execution after rollout, performance smoke checks and recommendation analytics.
- `DEFERRED`: TMDB keyword retrieval, distributed cache, media-type ML and full semantic/franchise graph.

## Next rollout gate

- `IMPLEMENTED BUT NOT DEPLOYED`: unified `Моё`/`Хочу посмотреть`/`Убрать` state path,
  cold-start confidence, canonical Profile → `Мой вкус`, versioned cache invalidation
  and compact Discover onboarding.
- `PLANNED`: controlled reset only after an explicit reviewed backup/runbook;
  disposable/staging migration execution, metadata backfill dry-run/write, API smoke,
  production performance measurements and deployment.
