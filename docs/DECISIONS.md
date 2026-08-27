# Recommendation decisions

## D1 — Normalized EMA instead of cumulative counts

`liked` is the strong positive signal and `watchlist` is intentionally weaker. Every blend is normalized and capped, so repeated actions do not make the profile unbounded. New positive interests reduce old weights through the `(1-alpha)` term. `archive/skip` excludes the concrete title and does not teach a permanent negative genre.

## D2 — Global taste plus media modifiers

Movie and TV share canonical feature distributions so affinity transfers across media. The 70/30 global/specific blend preserves cross-affinity while allowing a media-specific preference to win when evidence exists. TMDB rating/vote count remain quality/confidence features, not taste.

## D3 — Controlled relevance expansion

The final deck is selected from core, adjacent and discovery buckets. The target for ten cards is approximately 7/2/1, with fallback to the best available candidates. Discovery is never pure random: it needs a metadata touchpoint and sufficient quality.

## D4 — Soft media mix

Mix defaults to 70% movies / 30% TV, adapts from positive interaction history, and is bounded to 55–80% movies. Hard filters and relevance win over exact quotas; deterministic interleaving avoids a block of one media type.

## D5 — Migration gate

Recommendation migrations are `PRODUCTION`. They were applied in order after application-level backup and disposable verification; existing rows, primary-key changes, composite foreign keys, RLS/grants and service-role access were checked post-rollout.

## D6 — One canonical state/taste path

All web and Telegram status changes go through `media_state_service.apply_media_state`.
`Моё` is `liked` and a strong signal, `Хочу посмотреть` is `watchlist` and a weak
signal, and `Убрать` is `archive`, which excludes only the concrete title. A positive
status transition rebuilds the snapshot so the same title is not counted twice;
ratings rebuild the snapshot because they change signal strength.

## D7 — Profile is a snapshot, not a second recommender

Profile → `Мой вкус` reads `user_taste_profiles`. Collection statistics remain
collection statistics from `user_movies` and TV state. Cold start exposes maturity and
blends taste confidence gradually instead of switching personalization on at a fixed
interaction cliff.

## D8 — Deterministic bootstrap for existing users

Historical rows are not replayed through EMA because their chronological order is not
reliable. Existing users receive one order-independent weighted snapshot from current
liked/watchlist state; archive contributes zero. Metadata backfill is followed by a
replacement rebuild of that snapshot, never an additive replay.
