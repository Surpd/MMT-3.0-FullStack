# Технический аудит

## Critical

1. **Resolved: object-level authorization** — `backend/web_app/auth.py` now extracts signed Telegram identity into request context and `backend/web_app/api.py` rejects foreign legacy `user_id` values with 403. Covered by auth regression tests.
2. **Resolved: developer bypass scope** — `DEV_MODE=true` is accepted only for loopback requests; remote production-like requests still require valid Telegram auth. Covered by auth regression tests.
3. **Resolved: hardcoded client identity fallback** — `frontend/src/lib/api.ts` now requires Telegram identity or an explicit Vite development `VITE_DEV_USER_ID`.

## High

4. **Resolved: quiz answer was client-authoritative** — Quiz 2.0 sends public session questions while `/api/quiz/answer` validates question order/options and compares the submitted answer with server-side process-local state; replayed answers are rejected. Covered by API and Quiz 2.0 tests.
5. **Resolved: rating validation** — `/api/rate` now accepts only integer values 1–5 and allowlisted media types; covered by validation tests.
6. **Mitigated: async swipe writes** — frontend awaits the response and retries once; final failure is surfaced through Telegram notification. A durable queue is intentionally not introduced.
7. **Resolved: production Mini App URL hardcode** — `WEBAPP_URL` is config/env based, localhost is development-only, and production/staging require an explicit non-local value.
8. **Mitigated: Supabase public table exposure** — production schema was verified; RLS is enabled on the four application tables and `anon`/`authenticated` table privileges are revoked. No row policies exist because Telegram identity is enforced by the backend; the `rls_auto_enable()` cleanup remains; M.

## Medium

9. **Duplicate data access layers** — `services/database.py:20-24` creates another Supabase client and wraps legacy `DatabaseCRUD`; web API directly uses `_client`. Changes can diverge and testing is harder. Consolidate only after behavior capture; M/L.
10. **Resolved: duplicate movie upsert** — `database/crud.py` now writes the movie payload once, with characterization coverage; S.
11. **Mitigated: recommendation ratings ignored** — bounded rating signal is now included in liked genre affinity; deterministic signal tests added. Product evaluation is still required.
12. **Process-local caches** — `services/cache.py` stores pools/search results in memory; restart or multiple workers lose cache and FSM state. Expected correctness remains, but cost/UX is unstable; M.
13. **TMDB request policy is uneven** — `tmdb.py:53-61` has timeout but no retry/backoff/status classification; high-volume recommendation cascades can make many sequential calls. Add bounded instrumentation before optimization; M.
14. **Broad exception swallowing** — `web_app/api.py:20-31`, `search_service.py:79-100`, and several services suppress errors or return empty lists, making outages look like “no recommendations”. Improve structured logging and user-safe errors; M.

## Low / cleanup

15. `frontend/src/lib/movies.ts` contains a static 12-movie catalog and `ALL_GENRES`, with no active callers found; likely legacy/demo code.
16. `REDIS_URL` and `redis` dependency have no runtime usage; likely incomplete migration.
17. `backend/database/crud.py` and `services/database.py` contain comments indicating iterative fixes and duplicated methods; keep until a focused consolidation task.
18. `backend/make_docs.py`, `heal_db.py`, `tests/test_runner.py` look like scripts/manual tooling; no production caller found.

## Reliability and cost

Supabase failures retry only some paths; TMDB failures often collapse to empty results; Groq failure falls back to empty. Recommendation mix can make multiple discover/recommendation calls sequentially; AI itself is bounded to page 1 and only after ordinary search, which is a good cost-control decision. There is no metrics/tracing, request ID, circuit breaker or rate-limit visibility.
