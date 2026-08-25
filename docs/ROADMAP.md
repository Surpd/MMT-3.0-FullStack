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
- Add structured logs for request, user, upstream, latency and failure class; M.

## P2 — architecture

- Consolidate `SupabaseDatabase`/`DatabaseCRUD` and stop direct `_client` use in handlers; L.
- Add versioned schema/migrations and policy automation for future changes; current RLS remediation is documented and applied; L.
- Replace process-local cache/FSM assumptions if running multiple workers; M/L.
- Add bounded parallelism and deduplication around recommendation enrichment; M.

## P3 — product

- ~~Use explicit ratings as recommendation signal~~; bounded genre-affinity signal added; M.
- ~~Improve AI search with validated structured output and year matching~~; media-type/product personalization remain unchanged; M.
- Complete TV seasons/episodes only if product scope needs it; L.
- Add recommendation feedback analytics and quality evaluation; M/L.
