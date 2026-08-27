# My Movie Tracker — Verified Supabase Baseline

Initial read-only inspection date: 2026-08-27. Project: `My Movie Tracker` (`lsbrcbodwuytvgqawpdx`). A verified application-level backup preceded the recommendation rollout; post-rollout state is recorded below without secrets or row data.

## Verified schema

The live project was rechecked after rollout on 2026-08-27. The five recommendation migrations are applied in addition to the existing TV/movie migrations.

| Table | Rows | Primary key | Relevant foreign keys |
|---|---:|---|---|
| `public.movies` | 1102 | `(id, media_type)` | referenced by typed user/TV tables |
| `public.user_movies` | 759 | `(user_id, movie_id, media_type)` | `user_id → users.id`; `(movie_id, media_type) → movies` |
| `public.users` | 55 | `id` | referenced by user tables |
| `public.user_stats` | 53 | `user_id` | `user_id → users.id` |
| `public.tv_seasons` | 291 | `(tv_id, season_number)` | `tv_id → movies.id` |
| `public.tv_episodes` | 255 | `(tv_id, season_number, episode_number)` | season composite FK |
| `public.user_episode_progress` | 56 | `(user_id, tv_id, season_number, episode_number)` | user + episode composite FKs |
| `public.tv_notification_subscriptions` | 1 | `(user_id, tv_id)` | user + movie FKs |
| `public.tv_notification_deliveries` | 0 | `(user_id, tv_id, season_number, episode_number)` | user + movie FKs |

Observed columns include live-only legacy fields `movies.tmdb_rating`, `movies.studios`, `movies.next_episode`, and `user_movies.title`; these were not fully represented by the older documentation. The live `movies` table contains `keywords` after migration `20260827000200_add_movie_keywords.sql`.

## Initial RLS and policy state

Before remediation, RLS was disabled on all four public application tables: `movies`, `user_movies`, `users`, and `user_stats`, and `pg_policies` returned no policies for the public schema.

This was the Critical security finding that prompted the remediation. Application-layer Telegram identity checks do not replace database row-level isolation for direct Supabase Data API access.

## Post-remediation and recommendation rollout state

On 2026-08-25 the table-hardening block was applied through the Supabase plugin:

- RLS is enabled on all four tables;
- `anon` and `authenticated` have no SELECT/INSERT/UPDATE/DELETE privileges;
- `service_role` retains backend access;
- no row policies were added because Telegram `initData` is not a Supabase Auth JWT.
- recommendation migrations `20260827000100`–`20260827000500` are applied;
- post-rollout counts are `users=55`, `movies=1102`, `user_movies=759`, `user_taste_profiles=55`;
- all 64 legacy user/catalog media-type mismatches were reconciled and checked orphan counts are zero;
- typed movie/user identity is enforced by primary keys and composite foreign keys.

## Functions and advisors

- `public.rls_auto_enable()` exists as `SECURITY DEFINER` and is executable by both `anon` and `authenticated`.
- After remediation, security advisors report INFO for RLS enabled without row policies and WARN for public execution of that SECURITY DEFINER function.
- Performance advisors report an unindexed `user_movies_movie_id_fkey` and two currently unused movie indexes. These are non-blocking observations and were not changed.
- The pre-rollout 64 `user_movies` rows with a media type different from the catalog row were reconciled by `20260827000300_user_movies_media_identity.sql`.
- TV season, subscription and delivery rows retain valid typed references after the composite catalog identity migration.

## Required manual remediation

The current Telegram-auth architecture does not provide a Supabase Auth JWT, so `auth.uid()` cannot safely express ownership. The applied design and remaining cleanup are documented in [SUPABASE_RLS_REMEDIATION.md](SUPABASE_RLS_REMEDIATION.md) and [SQL draft](SUPABASE_RLS_REMEDIATION_DRAFT.sql).

Review or revoke access to `public.rls_auto_enable()` and its `ensure_rls` event trigger separately. Apply only through a separately approved migration after testing the actual Telegram/application access model. Do not enable RLS blindly: it can immediately block the current service-role/anon access pattern.
