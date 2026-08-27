# Данные и хранилище

The repository now contains additive SQL migrations for verified schema changes. A read-only inspection and applied RLS hardening are recorded in [SUPABASE_BASELINE.md](SUPABASE_BASELINE.md); public roles have no table access and no row policies are used because Telegram identity is enforced by the backend.

Read-only verification instructions are in [SUPABASE_BASELINE_CHECKLIST.md](SUPABASE_BASELINE_CHECKLIST.md). Production rollout records and post-change checks are in [SUPABASE_BASELINE.md](SUPABASE_BASELINE.md).

| Table | Fields observed | Reads | Writes |
|---|---|---|---|
| `users` | `id`, `username`, `first_name` | indirectly | `services/database.py:53-59` upsert |
| `profiles` | `id` | none in active facade | legacy `database/crud.py:25-30` |
| `user_stats` | `user_id`, `points`, `quiz_total`, `quiz_correct`, `current_streak`, `best_streak` | stats and quiz | ensure/update stats |
| `movies` | `id`, `media_type`, `title`, `year`, `rating_numeric`, `tmdb_vote_count`, `overview`, `poster_url`, `genres_array`, `keywords`, `actors`, `directors`, `production_countries`/`origin_country`, `runtime_mins`, `budget`, `revenue`, `seasons`, `number_of_episodes`, `tv_status`, `last_air_date`, `next_episode`, `metadata_updated_at` | library, details, recs | TMDB enrichment/upsert |
| `user_movies` | `user_id`, `movie_id`, `media_type`, `status`, `rating`, `last_action_id`, `updated_at`, `created_at` | context, library, details | swipe/rating/CRUD |
| `user_taste_profiles` | `user_id`, normalized feature JSONB fields, movie/TV modifiers, `interaction_count`, `profile_version`, `updated_at` | recommendation snapshot | EMA updates after positive swipe |

TV tracking is stored separately from the legacy movie relation:

- `tv_seasons` stores one row per real season;
- `tv_episodes` stores episode metadata, excluding episode zero from progress calculations;
- `user_episode_progress` stores watched episodes as rows, not mutable JSON;
- `tv_notification_subscriptions` stores explicit Telegram opt-in;
- `tv_notification_deliveries` is the idempotency log for release notifications.

Production migration history includes the TV tracking, movie metadata and recommendation changes. The five recommendation migrations `20260827000100`–`20260827000500` are applied; new tables keep backend-only access: RLS is enabled and `anon`/`authenticated` privileges are revoked.

Existing-user taste integration is a derived operation, not a data migration:
`backend/scripts/bootstrap_taste_profiles.py` builds an order-independent snapshot
from current `user_movies`, is dry-run by default, and replaces (rather than adds to)
`user_taste_profiles`. `backend/scripts/backfill_metadata.py` is likewise dry-run by
default; after an approved metadata write, rerun the deterministic taste bootstrap.

Production now uses `user_movies` primary key `(user_id, movie_id, media_type)` and `movies` primary key `(id, media_type)`. Migrations `20260827000300_user_movies_media_identity.sql` and `20260827000500_media_typed_catalog_identity.sql` reconciled legacy user rows from catalog `media_type`, recreated composite foreign keys, and added covering indexes. `20260827000400_add_swipe_idempotency.sql` adds only a bounded last-action marker, not an event log. The rollout reconciled all 64 observed mismatches; post-rollout orphan checks are zero.

Important consistency risks:

- `services/database.py` registers users in `users`, while legacy CRUD registers `profiles`.
- `DatabaseCRUD.save_movie` now performs one `movies.upsert`; regression coverage is in `backend/tests/test_data_access.py`.
- web routes still bypass the facade for some batch reads via `db._client` (`web_app/api.py`); this is an architecture follow-up, though recommendation enrichment itself is one local metadata query rather than candidate-by-candidate N+1.
- production RLS is enabled for the four application tables; public Data API table privileges are revoked and no row policies are intentionally defined.
# Recommendation state additions

`users` is preserved account identity. `movies` is the local `(id, media_type)`
metadata cache. `user_movies` is the current `(user_id, movie_id, media_type)`
relation and stores the current status/rating; `last_action_id` is a bounded retry
marker, not an event log. `user_taste_profiles` is the current normalized EMA
snapshot and is the canonical source for both Discover taste and Profile → `Мой вкус`.

Production status: these additions are `PRODUCTION`. Existing persistent state was
preserved; the derived taste snapshot was bootstrapped and then deterministically
rebuilt after metadata enrichment.
