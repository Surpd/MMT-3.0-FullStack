# Карта функций

| Feature | Status | Frontend | Backend | Database | External API | Notes |
|---|---|---|---|---|---|---|
| Mini App navigation | Working / appears complete | `App.tsx`, tabs | — | — | Telegram WebApp | UI tabs Discover, Search, Library, Profile, Quiz |
| Swipe recommendations | Partial | `DiscoverTab.tsx`, `DeckContext.tsx` | `/api/recommendations`, `/api/swipe` | `user_movies`, `movies` | TMDB | swipe waits for response and retries once; broader UX coverage remains |
| Library | Partial | `LibraryTab.tsx`, `ProfileTab.tsx` | `/api/library` | `user_movies`, `movies` | — | statuses are liked/watchlist/archive |
| Rating | Working / appears complete | `api.ts`, cards | `/api/rate` | `user_movies.rating` | TMDB on first save | server accepts integer 1–5 only |
| Search | Working / appears complete | `SearchTab.tsx` | `/api/search` | optional user context | TMDB | hybrid path |
| Natural-language AI search | Experimental | Search UI | `search_service.py` | — | Groq then TMDB | only reached after ordinary TMDB search returns empty |
| Quiz | Partial | `QuizTab.tsx` | `/api/quiz`, `/api/quiz/answer` | `user_stats`, process-local quiz cache | TMDB | server-authoritative one-time quiz token; bot remains separate callback flow |
| Telegram bot commands | Partial | — | `handlers/*` | same Supabase | TMDB | Mini App URL is read from `WEBAPP_URL`; bot quiz callback flow remains separate |
| TV support | Partial | typed fields and badges | TMDB + movie persistence | `movies.media_type`, seasons, tv_status | TMDB | extended persistence path has separate movie/tv branches |
| Baserow | Dead/unused or absent | — | — | — | — | no import/config/call found |
| Redis | Dead/unused or incomplete | — | `REDIS_URL` only read | — | Redis dependency only | runtime uses `MemoryCache`, not Redis |
