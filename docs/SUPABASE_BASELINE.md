# My Movie Tracker — Verified Supabase Baseline

Read-only inspection date: 2026-08-25. Project: `My Movie Tracker` (`lsbrcbodwuytvgqawpdx`). No SQL writes, migrations, schema changes, policy changes, or data changes were performed.

## Verified schema

The live project was rechecked read-only on 2026-08-26 before and after the TV tracking migration. The repository has no prior migration history; `add_tv_tracking` is the first recorded migration.

| Table | Rows | Primary key | Relevant foreign keys |
|---|---:|---|---|
| `public.movies` | 1013 | `id` | referenced by `user_movies.movie_id`, TV tables |
| `public.user_movies` | 67 | `(user_id, movie_id)` | `user_id → users.id`; `movie_id → movies.id` |
| `public.users` | 55 | `id` | referenced by user tables |
| `public.user_stats` | 53 | `user_id` | `user_id → users.id` |
| `public.tv_seasons` | 0 | `(tv_id, season_number)` | `tv_id → movies.id` |
| `public.tv_episodes` | 0 | `(tv_id, season_number, episode_number)` | season composite FK |
| `public.user_episode_progress` | 0 | `(user_id, tv_id, season_number, episode_number)` | user + episode composite FKs |
| `public.tv_notification_subscriptions` | 0 | `(user_id, tv_id)` | user + movie FKs |
| `public.tv_notification_deliveries` | 0 | `(user_id, tv_id, season_number, episode_number)` | user + movie FKs |

Observed columns include live-only legacy fields `movies.tmdb_rating`, `movies.studios`, `movies.next_episode`, and `user_movies.title`; these were not fully represented by the older documentation. TV tracking columns are now versioned in `supabase/migrations/20260826000100_add_tv_tracking.sql`.

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
