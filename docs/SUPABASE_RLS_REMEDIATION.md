# Supabase RLS remediation design

Status: table hardening applied on 2026-08-25. Optional `rls_auto_enable()` cleanup remains unapplied.

## Verified inputs

- Project: `My Movie Tracker` (`lsbrcbodwuytvgqawpdx`).
- `public.users`, `public.user_stats`, `public.user_movies`, and `public.movies` now have RLS enabled.
- `pg_policies` returns no policies for these tables by design.
- `anon` and `authenticated` now have no SELECT/INSERT/UPDATE/DELETE table privileges.
- The backend authenticates Telegram `initData` itself and stores the signed Telegram ID in the aiohttp request context.
- The backend uses `SUPABASE_KEY` through the Python Supabase client. The actual key type is not verified in the repository and must not be assumed.
- The frontend has no Supabase client; all data access goes through the backend.
- `user_id` is a Telegram numeric ID, not a Supabase Auth UUID/JWT subject.

## Applied current model

Use Supabase only as a backend-owned data store:

1. Verify that the backend `SUPABASE_KEY` is a server-only `service_role`/secret key and is not present in frontend configuration.
2. Enable RLS on all four public tables.
3. Revoke table privileges from `anon` and `authenticated` so direct Data API access cannot read or mutate application data.
4. Keep backend access through the server-only elevated key. Supabase's `service_role` bypasses RLS; the backend's Telegram identity boundary remains responsible for ownership checks.
5. Do not add `auth.uid()` policies: the current application does not create Supabase Auth sessions or JWTs containing the Telegram numeric ID.

This is intentionally a service-boundary design, not a claim that RLS itself understands Telegram identity. If direct browser-to-Supabase access is required later, first introduce a supported JWT/session bridge and design policies around that verified identity; do not compare `auth.uid()` to the current bigint Telegram IDs without a deliberate identity migration.

## Policy matrix

The recommended current-state matrix has no `anon` or `authenticated` policies. Their table privileges are revoked, so they cannot reach the tables through PostgREST. The backend service key is the only data-plane principal and bypasses RLS.

| Table | anon/authenticated | backend service | Ownership predicate |
|---|---|---|---|
| `users` | no SELECT/INSERT/UPDATE/DELETE | SELECT/INSERT/UPDATE through backend | checked by Telegram-authenticated backend code; no DB JWT predicate exists |
| `user_stats` | no SELECT/INSERT/UPDATE/DELETE | SELECT/INSERT/UPDATE through backend | backend derives `user_id` from validated Telegram identity |
| `user_movies` | no SELECT/INSERT/UPDATE/DELETE | SELECT/INSERT/UPDATE/DELETE through backend | backend derives and validates `user_id`; composite PK protects duplicate `(user_id, movie_id)` writes |
| `movies` | no SELECT/INSERT/UPDATE/DELETE | SELECT/INSERT/UPDATE through backend | global catalog, but still backend-owned because enrichment writes are privileged |

The backend must continue rejecting a client-supplied `user_id` that differs from the signed Telegram ID. RLS cannot compensate for a compromised or misconfigured service-role backend.

## `public.rls_auto_enable()`

Verified state:

- `public.rls_auto_enable()` is `SECURITY DEFINER`, owned by `postgres`, and has `search_path = pg_catalog`.
- Event trigger `ensure_rls` invokes it for `ddl_command_end`.
- The function enables RLS on newly created public tables but does not create policies.
- EXECUTE is granted to `PUBLIC`, `anon`, `authenticated`, and `service_role`.

Recommended action: remove the custom event trigger and function in a separately reviewed migration after confirming no operational dependency. Automatic RLS without matching policies can silently block legitimate access, while the public SECURITY DEFINER execute grant creates an unnecessary advisor finding. Do not replace it with another SECURITY DEFINER function. If the team wants automatic enforcement later, use a reviewed migration/CI check that validates both RLS state and required policies.

## Preconditions before applying

- Confirm the production `SUPABASE_KEY` role without printing or exposing its value.
- Confirm no frontend, bot, worker, or external job uses the anon/publishable key for these tables.
- Confirm the backend's service key has access to all current operations, including movie enrichment and user/stat upserts.
- Test the draft on a disposable branch or restored backup first.
- Capture a rollback plan for grants and RLS state; do not use production data changes as a test.
