# My Movie Tracker — Repository Instructions
## Project
My Movie Tracker is an existing production application.
Primary components:
- `frontend/` — React/Vite Telegram Mini App
- `backend/` — Python aiohttp backend and aiogram Telegram bot
- Supabase — persistent storage
- TMDB — movie and TV metadata
- Groq — optional AI fallback for natural-language search
- Render — backend hosting
- Cloudflare — frontend hosting
Project documentation is stored in `docs/`.
Before substantial changes, read the relevant files from:
- `docs/ARCHITECTURE.md`
- `docs/FEATURES.md`
- `docs/DATA_MODEL.md`
- `docs/API.md`
- `docs/INTEGRATIONS.md`
- `docs/DEPLOYMENT.md`
- `docs/RECOMMENDATIONS_ENGINE.md`
- `docs/SEARCH.md`
- `docs/TELEGRAM_BOT.md`
- `docs/TECH_DEBT.md`
- `docs/ROADMAP.md`
Code is the final source of truth when documentation is stale.
## General rules
- Preserve existing working behavior unless the task explicitly changes it.
- Prefer small, focused patches.
- Do not perform unrelated refactors.
- Do not deploy.
- Do not expose, print, commit, or rotate secrets.
- Do not modify production data.
- Do not run destructive database operations.
- Do not invent missing Supabase schema, RLS, production configuration, or environment values.
- Add regression tests for bug fixes when practical.
- Do not weaken tests simply to make them pass.
- Run relevant tests after changes.
- Inspect the final diff before considering the task complete.
## Security
Treat Telegram initData as the authentication source.
A `user_id` sent in query parameters, request JSON or frontend state is not authentication.
Authenticated identity must come from validated Telegram data.
Any developer authentication bypass must fail closed in production.
## Database
The audit found no authoritative SQL schema, migrations, foreign keys, indexes or RLS policies in the repository.
Do not assume production Supabase configuration.
Do not introduce schema changes until the current production schema has been captured or otherwise verified.
## Refactoring
Existing technical debt includes duplicate database access layers and direct Supabase client usage.
Before consolidating these layers:
1. identify callers;
2. capture behavior;
3. add tests;
4. refactor incrementally.
Avoid broad repository-wide rewrites.
## Recommendation engine
Recommendations are core product behavior.
Changes to recommendation scoring must be explainable and tested.
Explicit ratings are intended to become a meaningful preference signal but currently are not included in scoring.
## Search
Preserve cost-conscious search behavior:
ordinary/TMDB search first, AI fallback second.
Do not route ordinary exact-title/person/director searches through the LLM unnecessarily.
## Completion report
For implementation tasks, report:
- files changed;
- behavior changed;
- tests/checks executed;
- test results;
- remaining risks;
- suggested next task.
