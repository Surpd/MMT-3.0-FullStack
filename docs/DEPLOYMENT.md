# Deployment and operations

## Confirmed from code

- Backend entry point: `backend/main.py`.
- Required environment variables are checked in `backend/config.py`.
- HTTP server uses `PORT` (default `10000`) and binds `0.0.0.0`.
- Frontend production API base is hardcoded to `https://mmt-3-0-fullstack.onrender.com`.
- Frontend has `wrangler.jsonc` and Cloudflare Vite integration.
- Bot uses long polling, not webhook.
- `WEBAPP_URL` defaults to localhost only in development; `RUNTIME_ENV=production` or `staging` requires an explicit non-local URL.

## Not recoverable from repository

Render service settings, start/build commands, Cloudflare project/account, DNS, Telegram BotFather Mini App URL, Supabase project URL/schema/RLS, and production environment values are **Unknown / requires runtime or infrastructure verification.**

Do not put secret values in documentation. Backend names: `BOT_TOKEN`, `TMDB_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, `REDIS_URL`. `SUPABASE_KEY` is a legacy alias only when it contains a privileged service/secret key.
