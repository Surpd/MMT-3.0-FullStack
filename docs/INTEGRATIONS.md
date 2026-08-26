# Интеграции

## TMDB

`backend/services/tmdb.py` uses `https://api.themoviedb.org/3`, query API key, `language=ru-RU`, shared `aiohttp` session and a 30-second timeout from `config.py`. It calls search/multi, movie/tv details, recommendations, discover and network search. There is no retry/backoff in `TMDBClient._request`; callers inconsistently catch errors.

TV tracking additionally calls `/tv/{id}/season/{season_number}` only when a season is expanded (or by the notification job). TV details are refreshed from the database with a one-day metadata TTL; season/episode rows use a seven-day TTL. `backend/jobs/refresh_tv_notifications.py` is a one-shot Render Cron entrypoint and is intentionally not started inside the web process. For a repository-root Render service use `cd backend && python jobs/refresh_tv_notifications.py`.

## Supabase

`supabase.create_client` remains instantiated by the facade and legacy CRUD layer. Calls are synchronous SDK calls moved to threads. The facade retries selected connection/timeout errors three times; CRUD retries only `httpx.RequestError`. Production RLS is enabled on the four application tables, public table privileges are revoked, and backend access uses the server-only key confirmed during release operations.

## Groq

`GROQ_API_KEY` enables `openai/gpt-oss-120b` natural-language search. The request has a 10-second timeout; AI output is bounded, parsed as structured JSON with `title`, `year` and `media_type`, validated, deduplicated, and matched to TMDB by title/year/media type. Groq auth, model, rate-limit and other upstream failures are logged without exposing the key and safely return an empty AI fallback.

## Telegram

Bot uses aiogram polling. Mini App sends Telegram init data in `Authorization`. Bot commands and callbacks share Supabase/TMDB services with web API. No webhook code was found.

## Cloudflare / Render

Cloudflare-oriented frontend config exists in `frontend/wrangler.jsonc`; backend is Render-shaped by `PORT` and hardcoded frontend URL. No Render manifest, Dockerfile, CI/CD workflow or deployment command is tracked.

## Not found

Baserow imports, URLs and credentials: not found. Redis client usage: not found; only dependency and `REDIS_URL` exist. **Unknown / requires runtime or infrastructure verification** whether these exist outside the repository.
