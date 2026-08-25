# Recommendations

Entry point: `RecommendationService.get_next_movies`.

1. Load all `user_movies` rows and joined movie metadata.
2. Every interacted movie is blacklisted, so liked/watchlist/archive items are excluded.
3. Genre weights: liked +1, watchlist +0.35, archive −0.15; weights are `log(1 + score)`.
4. Keep the last three liked IDs for TMDB similar recommendations.
5. For fewer than 20 interactions, use high-vote “novice hits”. Otherwise combine genre discover cascade, similar-to-liked, and recent/trending discover results.
6. Score by genre affinity + TMDB rating + recency bonus − repeated-skipped-genre penalty.
7. Protect top five and shuffle the remainder with random noise.
8. Cache a per-user/filter pool for two hours; return ten items per cursor.
9. Missing movies are enriched from TMDB and persisted before serialization.

The bot obtains a batch of five from the same service (`services/bot_recs_service.py`); FSM stores that batch in memory.

Confirmed limitations:

- explicit ratings now adjust the liked genre signal in a bounded range: 1★ removes the positive liked contribution, 3★ is neutral, and 5★ adds a moderate bonus. The title remains blacklisted after interaction.
- archive/dislike is a permanent blacklist in context, not a time-bounded negative signal.
- caches are process-local, so multiple instances do not share pools.
- concurrent refreshes can create duplicate TMDB work and overwrite the same in-memory pool.
- `target_type` and filters are server-validated with bounded cursor/page/year/rating values.
