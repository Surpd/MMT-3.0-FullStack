# My Movie Tracker

Персональный Telegram Mini App и Telegram-бот для поиска фильмов и сериалов, рекомендаций, свайпов, библиотеки, рейтингов и квиза.

## Состав

- `frontend/` — React 19 + TypeScript + Vite/TanStack Start интерфейс, собираемый с Cloudflare Vite plugin.
- `backend/` — Python/aiogram бот и `aiohttp` HTTP API в одном процессе.
- Supabase — основное хранилище пользователей, фильмов, пользовательских статусов и статистики.
- TMDB — поиск, детали, рекомендации и discover.
- Groq — необязательный AI fallback для естественного поиска.

Подробности находятся в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) и связанных документах.

## Локальный запуск

Backend запускается из `backend/`, потому что импорты используют этот каталог как корень модулей:

```text
pip install -r backend/requirements.txt
python backend/main.py
```

Frontend:

```text
cd frontend
npm install
npm run dev
```

Нужны переменные окружения: `BOT_TOKEN`, `TMDB_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`; опционально `GROQ_API_KEY`, `REDIS_URL`, `DEV_MODE`, `PORT`, `RUNTIME_ENV`, `WEBAPP_URL`. Для `RUNTIME_ENV=production` или `staging` `WEBAPP_URL` обязателен; в development используется localhost по умолчанию. Authenticated E2E workflow описан в [docs/TESTING.md](docs/TESTING.md) и использует только отдельные `TEST_SUPABASE_URL`/`TEST_SUPABASE_KEY`.

Для локальных authenticated feature/E2E checks используется отдельный test auth harness. Запускайте backend только с изолированной dev/test Supabase-базой:

```powershell
$env:TEST_MODE = "true"
$env:TEST_USER_ID = "900000001"
$env:RUNTIME_ENV = "development"
$env:DEV_MODE = "false"
$env:TEST_SUPABASE_URL = "https://<isolated-test-project>.supabase.co"
$env:TEST_SUPABASE_KEY = "<isolated-test-key>"
Set-Location backend
python scripts/run_test_server.py
```

Подробные команды подготовки test user, frontend и HTTP-проверок находятся в [docs/TESTING.md](docs/TESTING.md).

## Проверки

- `python -m compileall -q backend` — проходит.
- `npm run lint` — требует отдельной проверки существующего форматирования frontend; узкий lint изменённых файлов проходит.
- `python -m unittest discover -s backend/tests -t backend -v` — запускает backend tests из корня репозитория.

## Deployment

Frontend содержит `frontend/wrangler.jsonc` и Cloudflare-oriented Vite config. Backend ожидает `PORT` и слушает `0.0.0.0`; frontend сейчас жёстко обращается к `https://mmt-3-0-fullstack.onrender.com`. Точный Render/Cloudflare проект, команды сборки, webhook и production secrets в репозитории не описаны: **Unknown / requires runtime or infrastructure verification.**
