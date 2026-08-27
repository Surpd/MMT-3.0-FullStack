# Локальное authenticated testing

## Зачем нужен harness

Production API принимает обычный пользовательский запрос только с валидным Telegram `Authorization: tma <initData>`. Для feature/integration/E2E-проверок Quiz, Library, Profile, Recommendations и Search криптографическая проверка Telegram не является предметом теста, поэтому локально можно явно включить test auth:

- backend: `TEST_MODE=true` и loopback-запрос с `X-Test-User-Id`;
- default test identity: `TEST_USER_ID=900000001`;
- header содержит только положительный integer user ID и не задаёт роль или права.

Без `TEST_MODE` header отклоняется. `production` и `staging` runtime его отклоняют и дополнительно блокируют запуск с `TEST_MODE=true`.

## Backend

Используйте отдельный test/dev Supabase project, если он доступен. Если отдельный проект невозможен, разрешён только явный local opt-in `ALLOW_PRODUCTION_TEST_USER=true` для reserved synthetic user `900000001`; без него bootstrap и E2E против текущего Supabase завершаются с ошибкой. Не добавляйте реальные credentials в документацию или репозиторий.

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

При старте в логах будет заметное сообщение `TEST AUTH ENABLED`.

`run_test_server.py` поднимает только aiohttp API и не запускает Telegram polling. Чтобы создать в изолированной базе пользователя, `user_stats`, 25 liked titles и первые ratings:

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

При наличии `TEST_SUPABASE_*` обычный `SUPABASE_*` никогда не используется. Для текущего MMT Supabase отдельный режим запуска требует `ALLOW_PRODUCTION_TEST_USER=true`; он проверяет reserved ID и разрешает менять только принадлежащие ему строки. Общий каталог `movies` только читается. Никаких global truncate/delete, schema, RLS или migrations не выполняется.

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

## Один browser E2E workflow

Production использует Telegram initData и production Supabase. Local development может использовать обычный `DEV_MODE`, но automated E2E использует отдельный `TEST_MODE` и test target. Предпочтителен `TEST_SUPABASE_URL`/`TEST_SUPABASE_KEY`; для текущего MMT Supabase нужен явный `ALLOW_PRODUCTION_TEST_USER=true`. Без test target и без opt-in E2E завершается fail-fast; secrets не хранятся в git и не попадают во frontend.

Шаблон переменных: `.env.test.example`. Перед запуском нужно один раз получить изолированный test Supabase project и задать его URL/key в окружении. Проект не создаётся автоматически, а production credentials никогда не используются как fallback.

Из `frontend/` одна команда подготавливает test user, затем Playwright автоматически запускает backend readiness endpoint и Vite frontend, выполняет smoke suite и завершает оба процесса:

```powershell
Set-Location frontend
$env:TEST_MODE = "true"
$env:VITE_TEST_MODE = "true"
$env:TEST_USER_ID = "900000001"
$env:VITE_TEST_USER_ID = "900000001"
$env:RUNTIME_ENV = "development"
$env:ALLOW_PRODUCTION_TEST_USER = "true"
npm run test:e2e:smoke
```

Если задан отдельный target, вместо opt-in задайте `TEST_SUPABASE_URL` и `TEST_SUPABASE_KEY`; он будет выбран приоритетно. `npm run test:e2e` запускает тот же workflow; `test:e2e:smoke` явно ограничивает smoke-тегом. Без test target и без `ALLOW_PRODUCTION_TEST_USER=true` команда fail-fast и не стартует приложение. Backend получает target только из выбранного режима, browser получает только `VITE_API_BASE`, `VITE_TEST_MODE` и test user ID — Supabase key в browser env отсутствует.

Bootstrap проверяет, что `TEST_USER_ID=900000001` отсутствует либо уже принадлежит только synthetic `mmt_test_user`, затем создаёт/обновляет его `users`, legacy `profiles`, `user_stats`, 25 liked library rows и первые ratings из существующего movie+TV каталога. Reset действует только на `TEST_USER_ID`; общий `movies` только читается. При конфликте identity или неполном каталоге destructive reset не выполняется. Schema, RLS и migrations не меняются. `backend/scripts/run_test_server.py` поднимает только aiohttp API и не запускает Telegram polling.

Уровни проверки: unit → backend integration → authenticated API smoke → browser E2E. Маленькая backend logic задача использует targeted unit/integration; API/authenticated feature — backend integration + authenticated API smoke; frontend UX/navigation — targeted frontend checks + Playwright smoke; critical user flow — Playwright E2E. Telegram auth проверяется отдельно signed fixtures (valid initData, invalid hash, missing/malformed data, identity extraction и guards), без test bypass.

Не запускайте full browser E2E для каждой pure-function правки. Если test environment не настроен, финальный отчёт должен назвать отсутствующий `TEST_SUPABASE_*` prerequisite; feature нельзя считать непроверенным только из-за отсутствия Telegram initData, поскольку для него предусмотрен test harness.

Browser smoke использует реальный локальный backend и deterministic test target: App boot/navigation, Profile, movie+TV Library, unlocked My Library Quiz (start/answer/exit) и переход в Profile во время pending Quiz response. Authenticated API smoke остаётся in-memory проверкой stats, library, Quiz meta и старта library Quiz.
