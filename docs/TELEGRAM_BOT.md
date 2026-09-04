# Telegram bot

## Commands and entry points

- `/start` — ensure user and show main keyboard.
- `/refresh` — rebuild keyboard.
- `/app` — show Mini App button.
- `🎲 Что посмотреть?` — generate five recommendations and navigate them through FSM callbacks.
- `🔍 Поиск` + free text — hybrid search; pagination callback `search_page_*`.
- `🗄 Библиотека` — library menu and paginated statuses.
- `🧠 Квиз` — quiz flow and correct/wrong callbacks.
- movie callbacks — status, details, similar, reroll.
- `📊 Статистика` — stats response.

The main keyboard also exposes `🎬 Рекомендации`, `🔎 Найти`, `📚 Моё`,
`🔖 В планах`, `📺 Сериалы`, `📊 Профиль` and `🌐 Открыть приложение`.
Search can be explicitly typed as movie, TV or person; person results use the
shared TMDB person/combined-credits service. Movie/TV actions use the shared
`media_state_service`, ratings use `apply_rating`, recommendations use the
same `RecommendationService` flow and filters as the Mini App, and TV progress
uses `tv_service`/the existing episode tables. Telegram callback data is
parsed by `services/telegram_ui.py` and bounded to compact allow-listed actions.

Routers are included in `backend/main.py`. `UserMiddleware` calls `db.ensure_user` for every message and callback. `ThrottlingMiddleware` applies a one-second per-process per-user limit and rejects message text over 150 characters.

## State and coupling

FSM holds current search query, filter input and recommendation batch in memory.
Restarting the process loses only this ephemeral navigation state; persistent
media state and TV progress remain in Supabase. Bot uses the same
service/database objects as web API, with Telegram rendering isolated in
small UI helpers. `WEBAPP_URL` is read from backend config; localhost is
development-only.

No webhook implementation was found; startup explicitly calls `delete_webhook` and starts polling.
