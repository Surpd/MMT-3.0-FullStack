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

Routers are included in `backend/main.py`. `UserMiddleware` calls `db.ensure_user` for every message and callback. `ThrottlingMiddleware` applies a one-second per-process per-user limit and rejects message text over 150 characters.

## State and coupling

FSM holds current search query and recommendation batch in memory. Restarting the process loses that state. Bot uses the same service/database objects as web API, but some UI and callback logic remains duplicated in handlers. `WEBAPP_URL` is now read from backend config; localhost is development-only.

No webhook implementation was found; startup explicitly calls `delete_webhook` and starts polling.
