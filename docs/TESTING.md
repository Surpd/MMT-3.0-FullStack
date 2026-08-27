# Локальное authenticated testing

## Зачем нужен harness

Production API принимает обычный пользовательский запрос только с валидным Telegram `Authorization: tma <initData>`. Для feature/integration/E2E-проверок Quiz, Library, Profile, Recommendations и Search криптографическая проверка Telegram не является предметом теста, поэтому локально можно явно включить test auth:

- backend: `TEST_MODE=true` и loopback-запрос с `X-Test-User-Id`;
- default test identity: `TEST_USER_ID=900000001`;
- header содержит только положительный integer user ID и не задаёт роль или права.

Без `TEST_MODE` header отклоняется. `production` и `staging` runtime его отклоняют и дополнительно блокируют запуск с `TEST_MODE=true`.

## Backend

Используйте отдельный test/dev Supabase project. Не направляйте bootstrap в production project и не добавляйте реальные credentials в документацию или репозиторий.

```powershell
$env:TEST_MODE = "true"
$env:TEST_USER_ID = "900000001"
$env:RUNTIME_ENV = "development"
$env:DEV_MODE = "false"
python backend/main.py
```

При старте в логах будет заметное сообщение `TEST AUTH ENABLED`.

Чтобы создать в изолированной базе пользователя, `user_stats`, 25 liked titles и первые ratings:

```powershell
$env:TEST_MODE = "true"
$env:TEST_USER_ID = "900000001"
$env:RUNTIME_ENV = "development"
$env:TEST_SUPABASE_URL = "https://<isolated-test-project>.supabase.co"
$env:TEST_SUPABASE_KEY = "<isolated-test-key>"
Set-Location backend
python scripts/bootstrap_test_user.py
Set-Location ..
```

Bootstrap требует отдельные `TEST_SUPABASE_URL` и `TEST_SUPABASE_KEY`, поэтому обычный `SUPABASE_URL` приложения случайно не используется. Данные остаются только в этом isolated test project; схема, RLS и migrations не меняются.

Authenticated HTTP request:

```powershell
curl.exe -H "X-Test-User-Id: 900000001" http://127.0.0.1:10000/api/stats
curl.exe -H "X-Test-User-Id: 900000001" "http://127.0.0.1:10000/api/quiz/meta"
curl.exe -H "X-Test-User-Id: 900000001" "http://127.0.0.1:10000/api/quiz?mode=library"
```

Frontend against the local backend:

```powershell
Set-Location frontend
$env:VITE_API_BASE = "http://127.0.0.1:10000"
$env:VITE_TEST_MODE = "true"
$env:VITE_TEST_USER_ID = "900000001"
npm run dev
```

The frontend sends `X-Test-User-Id` only when `import.meta.env.DEV` and `VITE_TEST_MODE=true`. Normal Telegram `initData` behavior is unchanged, and a production build cannot activate this helper through these variables.

## Политика тестов

Authentication tests остаются отдельными и используют signed Telegram fixtures: valid signature, invalid hash, missing/malformed initData, identity extraction and local/production-like guards. Feature tests may use the test header because they test authenticated product behavior, not Telegram HMAC validation.

Run the backend suite from the repository root:

```powershell
python -m unittest discover -s backend/tests -t backend -v
```

The authenticated smoke test covers stats, library, Quiz meta and starting a library Quiz session with a 25-title test user state. It uses an in-memory fixture; the bootstrap script is for real local backend/E2E checks.
