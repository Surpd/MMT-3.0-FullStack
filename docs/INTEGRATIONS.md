# Интеграции

## TMDB

`backend/services/tmdb.py` uses `https://api.themoviedb.org/3`, query API key, `language=ru-RU`, shared `aiohttp` session and a 30-second timeout from `config.py`. It calls search/multi, movie/tv details, recommendations, discover and network search. There is no retry/backoff in `TMDBClient._request`; callers inconsistently catch errors.

## Supabase

`supabase.create_client` remains instantiated by the facade and legacy CRUD layer. Calls are synchronous SDK calls moved to threads. The facade retries selected connection/timeout errors three times; CRUD retries only `httpx.RequestError`. Production RLS is enabled on the four application tables, public table privileges are revoked, and backend access uses the server-only key confirmed during release operations.

## Groq

`GROQ_API_KEY` enables `llama-3.3-70b-versatile` natural-language search. The request has a 10-second timeout; AI output is bounded, parsed as structured JSON, validated, deduplicated, and matched to TMDB by title/year.

## Telegram

Bot uses aiogram polling. Mini App sends Telegram init data in `Authorization`. Bot commands and callbacks share Supabase/TMDB services with web API. No webhook code was found.

## Cloudflare / Render

Cloudflare-oriented frontend config exists in `frontend/wrangler.jsonc`; backend is Render-shaped by `PORT` and hardcoded frontend URL. No Render manifest, Dockerfile, CI/CD workflow or deployment command is tracked.

## Not found

Baserow imports, URLs and credentials: not found. Redis client usage: not found; only dependency and `REDIS_URL` exist. **Unknown / requires runtime or infrastructure verification** whether these exist outside the repository.
