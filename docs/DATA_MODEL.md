# Данные и хранилище

The repository contains no authoritative SQL migrations. A read-only inspection and applied RLS hardening are recorded in [SUPABASE_BASELINE.md](SUPABASE_BASELINE.md); public roles have no table access and no row policies are used because Telegram identity is enforced by the backend.

Read-only verification instructions are in [SUPABASE_BASELINE_CHECKLIST.md](SUPABASE_BASELINE_CHECKLIST.md). No production mutation was performed during this maintenance pass.

| Table | Fields observed | Reads | Writes |
|---|---|---|---|
| `users` | `id`, `username`, `first_name` | indirectly | `services/database.py:53-59` upsert |
| `profiles` | `id` | none in active facade | legacy `database/crud.py:25-30` |
| `user_stats` | `user_id`, `points`, `quiz_total`, `quiz_correct`, `current_streak`, `best_streak` | stats and quiz | ensure/update stats |
| `movies` | `id`, `title`, `year`, `rating_numeric`, `overview`, `poster_url`, `genres_array`, `media_type`, `actors`, `directors`, `runtime_mins`, `budget`, `revenue`, `seasons`, `number_of_episodes`, `tv_status`, `last_air_date`, `next_episode`, `metadata_updated_at` | library, details, recs | TMDB enrichment/upsert |
| `user_movies` | `user_id`, `movie_id`, `media_type`, `status`, `rating`, `updated_at`, `created_at` | context, library, details | swipe/rating/CRUD |

TV tracking is stored separately from the legacy movie relation:

- `tv_seasons` stores one row per real season;
- `tv_episodes` stores episode metadata, excluding episode zero from progress calculations;
- `user_episode_progress` stores watched episodes as rows, not mutable JSON;
- `tv_notification_subscriptions` stores explicit Telegram opt-in;
- `tv_notification_deliveries` is the idempotency log for release notifications.

The additive migration is `supabase/migrations/20260826000100_add_tv_tracking.sql`. All new tables keep backend-only access: RLS is enabled and `anon`/`authenticated` privileges are revoked.

`user_movies` is treated as unique on `(user_id, movie_id)` by upsert calls. The code assumes relations `user_movies → movies` and a user foreign key, but constraints are not verifiable statically.

Important consistency risks:

- `services/database.py` registers users in `users`, while legacy CRUD registers `profiles`.
- `DatabaseCRUD.save_movie` now performs one `movies.upsert`; regression coverage is in `backend/tests/test_data_access.py`.
- web routes bypass the facade via `db._client` (`web_app/api.py:121`, `240`, `333`).
- production RLS is enabled for the four application tables; public Data API table privileges are revoked and no row policies are intentionally defined.
