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
| GET | `/api/stats` | user stats | `user_id` | stats + level/title |
| GET | `/api/quiz` | generate quiz | authenticated identity | question/options/one-time `quiz_id`; correct answer is server-side |
| POST | `/api/quiz/answer` | update quiz stats | `user_id,quiz_id,answer` | message + stats + server result |
| GET | `/api/search/tags` | personalized search tags | optional `user_id` | `{tags}` |

Authentication is validated in middleware and stored as trusted request identity. Legacy `user_id` values are accepted only when they match that identity; mismatches return 403. Local development bypass is limited to loopback requests with `DEV_MODE=true`.
