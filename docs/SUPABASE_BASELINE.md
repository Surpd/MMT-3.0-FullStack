# My Movie Tracker — Verified Supabase Baseline

Read-only inspection date: 2026-08-25. Project: `My Movie Tracker` (`lsbrcbodwuytvgqawpdx`). No SQL writes, migrations, schema changes, policy changes, or data changes were performed.

## Verified schema

| Table | Rows | Primary key | Relevant foreign keys |
|---|---:|---|---|
| `public.movies` | 998 | `id` | referenced by `user_movies.movie_id` |
| `public.user_movies` | 66 | `(user_id, movie_id)` | `user_id → users.id`; `movie_id → movies.id` |
| `public.users` | 53 | `id` | referenced by `user_movies.user_id`, `user_stats.user_id` |
| `public.user_stats` | 51 | `user_id` | `user_id → users.id` |

Observed columns match the application assumptions in `DATA_MODEL.md`, including `user_movies.rating smallint`, `media_type`, timestamps, and composite uniqueness represented by the primary key.

## Initial RLS and policy state

Before remediation, RLS was disabled on all four public application tables: `movies`, `user_movies`, `users`, and `user_stats`, and `pg_policies` returned no policies for the public schema.

This was the Critical security finding that prompted the remediation. Application-layer Telegram identity checks do not replace database row-level isolation for direct Supabase Data API access.

## Post-remediation state

On 2026-08-25 the table-hardening block was applied through the Supabase plugin:

- RLS is enabled on all four tables;
- `anon` and `authenticated` have no SELECT/INSERT/UPDATE/DELETE privileges;
- `service_role` retains backend access;
- no row policies were added because Telegram `initData` is not a Supabase Auth JWT.

## Functions and advisors

- `public.rls_auto_enable()` exists as `SECURITY DEFINER` and is executable by both `anon` and `authenticated`.
- After remediation, security advisors report INFO for RLS enabled without row policies and WARN for public execution of that SECURITY DEFINER function.
- Performance advisors report an unindexed `user_movies_movie_id_fkey` and two currently unused movie indexes. These are non-blocking observations and were not changed.
- Supabase reports no migration history for this project.

## Required manual remediation

The current Telegram-auth architecture does not provide a Supabase Auth JWT, so `auth.uid()` cannot safely express ownership. The applied design and remaining cleanup are documented in [SUPABASE_RLS_REMEDIATION.md](SUPABASE_RLS_REMEDIATION.md) and [SQL draft](SUPABASE_RLS_REMEDIATION_DRAFT.sql).

Review or revoke access to `public.rls_auto_enable()` and its `ensure_rls` event trigger separately. Apply only through a separately approved migration after testing the actual Telegram/application access model. Do not enable RLS blindly: it can immediately block the current service-role/anon access pattern.
