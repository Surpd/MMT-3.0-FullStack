# HTTP API

All routes are registered in `backend/main.py:73-85`. Except `/` and OPTIONS, auth middleware requires `Authorization: tma <Telegram initData>` unless `DEV_MODE=true`.

| Method | Path | Purpose | Input | Output / caller |
|---|---|---|---|---|
| GET | `/` | health check | — | text; Render health check |
| GET | `/api/movies` | legacy/default recommendation deck | `user_id`, `cursor` | `{ok,movies,next_cursor}`; frontend |
| GET | `/api/recommendations` | filtered recommendation deck | `user_id`, `skip`, optional `target_type`, `min_year`, `min_rating` | same; `DeckContext` |
| POST | `/api/swipe` | persist liked/archive/watchlist | JSON `user_id,movie_id,action,media_type` | `{ok}`; Discover/Search/Library |
| POST | `/api/rate` | persist 1–5 rating | JSON `user_id,movie_id,rating,media_type`; rating is integer 1–5 | `{ok}` |
| GET | `/api/library` | paginated library | `user_id,status,page` | `{ok,movies}` |
| GET | `/api/search` | hybrid search | `user_id,q` (q capped 100 chars) | `{ok,movies}` |
| GET | `/api/movie`, `/api/movie-details` | detail/enrichment | `movie_id,user_id,media_type` | detail + user status/rating |
| GET | `/api/tv/progress` | lazy TV season/episode metadata and user progress | `tv_id,user_id` | progress, next episode, computed state |
| GET | `/api/tv/season` | load one season's episodes on demand | `tv_id,season_number,user_id` | season episodes + watched flags |
| POST | `/api/tv/episode-progress` | mark/unmark released episode | `user_id,tv_id,season_number,episode_number,watched` | updated progress |
| POST | `/api/tv/season-progress` | mark/unmark all released episodes in a season | `user_id,tv_id,season_number,watched` | updated progress |
| POST | `/api/tv/notifications` | opt in/out of release notifications | `user_id,tv_id,enabled` | subscription state |
| GET | `/api/stats` | user stats | `user_id` | stats + level/title |
| GET | `/api/quiz?mode=cinema\|library\|daily` | create Quiz 2.0 session | authenticated identity | public question batch; library gate and daily state when applicable |
| POST | `/api/quiz/answer` | answer Quiz 2.0 question | `session_id,question_id,answer,elapsed_ms` | server result, score/combo, stats and final result |
| GET | `/api/search/tags` | personalized search tags | optional `user_id` | `{tags}` |

Authentication is validated in middleware and stored as trusted request identity. Legacy `user_id` values are accepted only when they match that identity; mismatches return 403. Local development bypass is limited to loopback requests with `DEV_MODE=true`.
