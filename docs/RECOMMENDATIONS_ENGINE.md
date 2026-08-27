# Discover Recommendations v1

Статусы: `PRODUCTION` — уже работает в production; `IMPLEMENTED BUT NOT DEPLOYED` — код готов, но rollout ещё не завершён; `PLANNED` — не написано; `DEFERRED` — сознательно отложено.

## Current flow

`Discover → taste → candidates → filters → scoring → buckets → diversity → mix → reasons → deck → swipe → taste update`

Entry point: `backend/services/recommendation_service.py:RecommendationService.get_next_movies`.

Canonical state entry point: `backend/services/media_state_service.py:apply_media_state`.
Web Discover/Search/Library and Telegram callbacks use the same state-to-taste path;
ratings use `apply_rating`. `Моё` maps to `liked`, `Хочу посмотреть` to `watchlist`,
and `Убрать` to `archive`.

## Product decisions

- `liked` — основной positive signal; `watchlist` — более слабый positive signal.
- `archive/skip` — exclusion конкретной `(movie_id, media_type)`, не dislike и не постоянный genre penalty.
- Taste — normalized EMA: старые веса умножаются на `(1-alpha)`, title signal добавляется с `alpha`, затем профиль нормализуется и обрезается cap-ом.
- Global profile переносит affinity между movie и TV; `movie_modifiers`/`tv_modifiers` дают media-specific поправку.
- TMDB rating/vote count — quality/confidence, не taste signal.
- Final deck использует мягкие core/adjacent/discovery buckets и default movie/TV mix 70/30.
- Hard filters (`min_year`, `max_year`, `min_rating`) не ослабляются ради заполнения.
- Reasons выбираются после score/bucket classification и должны соответствовать ненулевому breakdown signal.

## Taste profile

В production после migrations `20260827000100`–`20260827000500`. `user_taste_profiles` хранит `genres_jsonb`, `keywords_jsonb`, `directors_jsonb`, `countries_jsonb`, `eras_jsonb`, `movie_modifiers_jsonb`, `tv_modifiers_jsonb`, `interaction_count`, `profile_version`, `updated_at`.

Текущие alpha в `recommendation_service.py`:

- liked: genres `.09`, keywords `.07`, directors `.04`, countries `.025`, eras `.025`;
- watchlist: genres `.025`, keywords `.02`, directors `.01`, countries `.0075`, eras `.01`;
- rating multiplier для liked: `1★=0`, `2★=.25`, `3★=.5`, `4★=.8`, `5★=1`.

`archive` не вызывает blend. При отсутствии snapshot первый swipe строит fallback из остальных `user_movies`, исключая текущую `(movie_id, media_type)`, затем применяет текущий item ровно один раз. Повтор frontend swipe с тем же `action_id` не повторяет EMA.

Cold start is confidence-aware: 0 positive interactions uses broad high-confidence
retrieval; 1–3, 4–9 and 10+ interactions progressively blend personal taste into
scoring (confidence grows from 0.12/interaction to 0.35, then 0.60 and finally 1.0).
This prevents a single liked title from locking the deck to one genre.

Existing-user rollout uses `backend/scripts/bootstrap_taste_profiles.py`. It aggregates
the current `user_movies` snapshot order-independently (liked × rating multiplier,
watchlist × weak alpha, archive × 0), normalizes/caps once, and writes global plus
movie/TV modifiers. It is dry-run by default and requires `--write`; reruns replace
the snapshot and therefore do not double-count history. After metadata enrichment,
the same deterministic rebuild is the safe way to add newly available feature groups.
New users keep an empty snapshot and learn through the normal EMA path.

## Taxonomy and metadata

Единый source of truth: `backend/utils/genres.py`. Он содержит TMDB id/display labels, aliases, canonical names и `normalize_tmdb_genre`/`normalize_title_genres`; тот же код используют `taste_service`, recommender, model и TMDB mapping. Canonical genre id связывает movie и TV (`Crime`, `Mystery`, `Thriller`, etc.) независимо от TMDB label.

Локальные `movies.keywords`, `directors`, `production_countries`/`origin_country`, `tmdb_vote_count` используются для scoring без detail/keywords/credits N+1. Если deep metadata отсутствует, TMDB candidate остаётся допустимым и ранжируется по доступным полям.

## Retrieval

Для established user источники добавляются в один deduplicated pool по `(id, media_type)`:

1. `discover/{movie|tv}` по двум strongest canonical genres;
2. `discover` по adjacent genres;
3. `/{media_type}/{id}/recommendations` для до трёх recent liked seeds;
4. recent release и popular/high-confidence `discover`;
5. controlled exploration по adjacent genre.

Источники запускаются параллельно, ошибки одного source не отменяют остальные. `_RetrievalBudget` ограничивает generation общим максимумом 18 TMDB requests, до 4 sequential pages на source и отдельными source caps. Если первая страница не проходит hard filters, page 2/следующие запрашиваются последовательно; `total_pages` учитывается. Цель — порядка 80–120 raw candidates, но pool может быть меньше при строгих фильтрах/ошибках.

TMDB keyword endpoint не добавлялся: keywords берутся из локальной metadata, чтобы не создавать candidate × keywords N+1.

## Scoring and final deck

`_score_candidates` сохраняет decomposition: `genres`, `keywords`, `director`, `country`, `era`, `media_modifier`, `taste_match`, `quality`, `exploration`, `skip_penalty`. Каждый feature match — `0.7 * global_dot + 0.3 * media_modifier_dot`; сначала считается `personal_match = .35 genre + .20 keyword + .15 director + .10 country + .10 era + .10 media_modifier`, затем runtime `taste_match = confidence * personal_match`.

`quality = (vote_average / 10) * min(1, log10(vote_count + 1) / 5)`, а `FinalScore = taste_match + .10*quality + .05*exploration - skip_penalty`. Popularity используется retrieval-ом, но не отдельным dominant rank bonus; recency bonus отсутствует.

Bucket classification: высокий personal match — `core`; частичное meaningful совпадение/adjacent source — `adjacent`; quality candidate с metadata touchpoint и меньшим personal match — `discovery`. `_select_buckets` для batch 10 сначала старается выбрать 7/2/1, затем добирает лучшими доступными кандидатами.

Diversity защищает top 5, затем мягко штрафует повтор director, пересечение canonical genres/keywords, одинаковую collection и повтор source. Для mix применяется deterministic interleave с мягким target ratio. Default 70/30, adaptive ratio ограничен movie 55–80% (TV 20–45%) и считается по positive movie/TV interactions.

Reasons: `genres`, `keywords`, `director`, `country`, `era`, `quality`, `adjacent`, `discovery`, `fallback`. Adjacent/discovery выбираются после bucket classification; “популярный/качественный” используется только при реальном quality signal.

## Profile and collection state

`Profile → Мой вкус` reads distributions from `user_taste_profiles` only. Collection
counts and movie/TV totals still come from `user_movies`; profile does not rebuild a
second taste algorithm from the library. The API returns maturity (`empty`, `early`,
`forming`, `mature`), confidence, genres, themes, countries, directors and eras.
New users see a compact Discover onboarding card with a Search seed path.

## Cache and rollout state

Pool key включает user, filters и `profile_version`; profile update после liked/watchlist увеличивает version, archive также bump-ит version без изменения taste. Per-user generation lock предотвращает конкурентную двойную генерацию внутри процесса. `session_{user_id}` хранит до 100 недавно возвращённых `(id, media_type)` для lightweight exclusion. Frontend сохраняет prefetch threshold `deck.length <= 5` и посылает один `action_id` на обе retry attempts.

Current status: recommendation code, state-path changes, tests, migrations, bootstrap,
metadata backfill and backend deployment are `PRODUCTION`. Production checks confirmed
55 profiles, unchanged persistent row counts, zero media mismatches and zero checked
orphans. Frontend build passed; Cloudflare deployment status is not exposed by the
repository or connected deployment tool.

The metadata operation is `backend/scripts/backfill_metadata.py --dry-run` followed
by an explicitly approved `--write` run. Dry-run performs no TMDB requests; it reports
the bounded candidate count and estimated one-details-request-per-title budget.

## Explicitly not implemented

Нельзя считать production: distributed cache/lock между несколькими backend instances, feedback analytics/evaluation, ML/media model, TMDB keyword retrieval, franchise graph beyond available collection metadata and automatic stale-idempotency cleanup. Эти пункты `PLANNED` или `DEFERRED`, а не скрытые части v1.
