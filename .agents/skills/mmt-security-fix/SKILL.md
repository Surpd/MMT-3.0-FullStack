---
name: mmt-security-fix
description: Fix authentication, authorization and identity-boundary issues in My Movie Tracker. Use for Telegram Mini App authentication, initData validation, user impersonation prevention, DEV_MODE authentication bypasses, hardcoded fallback identities, object-level authorization, or security regression tests.
---
# My Movie Tracker Security Fix
Work only on the requested security issue.
## Required preparation
Read:
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/TECH_DEBT.md`
- `docs/TELEGRAM_BOT.md`
Inspect:
- authentication middleware;
- all routes receiving `user_id`;
- frontend identity construction;
- local development authentication behavior;
- tests covering authentication.
## Identity rule
The signed Telegram identity is authoritative.
Never treat `user_id` from:
- query parameters;
- request JSON;
- frontend state;
- local storage;
as authenticated identity.
After Telegram initData validation:
1. extract the signed Telegram user ID;
2. expose it to request handlers through request context or an equivalent trusted mechanism;
3. make handlers operate on that identity;
4. where a legacy `user_id` parameter remains, require it to equal the authenticated identity or ignore it safely.
## DEV_MODE
Do not permit an environment-variable typo or accidental production setting to expose the API.
Development bypass behavior must be explicitly local and fail closed outside intended development conditions.
Do not introduce a permanent production fallback identity.
## Testing
Cover at minimum where applicable:
- valid own-user request;
- valid Telegram signature with another requested `user_id`;
- invalid Telegram signature;
- missing auth;
- malformed initData;
- local development behavior;
- production-like configuration with development bypass disabled.
Use 401 for unauthenticated requests and 403 for authenticated-but-forbidden requests when consistent with the existing API.
## Scope
Do not refactor unrelated API architecture.
Do not redesign Supabase access while fixing authentication.
If RLS cannot be verified from the repository, report that separately rather than assuming it is safe.
