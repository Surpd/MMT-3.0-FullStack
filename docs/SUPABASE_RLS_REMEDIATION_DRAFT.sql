-- My Movie Tracker — RLS remediation draft
-- STATUS: TABLE HARDENING APPLIED 2026-08-25. DO NOT RE-RUN BLINDLY.
--
-- This draft assumes the backend uses a server-only Supabase service_role/secret
-- key and that the frontend never calls Supabase directly. Verify that assumption
-- before applying. The current Telegram initData is not a Supabase Auth JWT, so
-- this draft intentionally does not use auth.uid().
--
-- Recommended rollout:
--   1. Verify key type and all Supabase callers outside this repository.
--   2. Test on a disposable branch/restore.
--   3. Apply the table hardening separately from removal of ensure_rls.
--   4. Run application tests and a Telegram-authenticated smoke test.
--   5. Run Supabase security/performance advisors.

BEGIN;

-- Preflight: fail rather than silently targeting a different schema.
DO $$
BEGIN
  IF to_regclass('public.users') IS NULL
     OR to_regclass('public.user_stats') IS NULL
     OR to_regclass('public.user_movies') IS NULL
     OR to_regclass('public.movies') IS NULL THEN
    RAISE EXCEPTION 'RLS draft preflight failed: expected public application tables are missing';
  END IF;
END
$$;

-- The current app has no Supabase Auth identity that can be used in a policy.
-- Deny direct Data API access to the public roles instead of inventing an
-- auth.uid() predicate that cannot represent Telegram numeric IDs.
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_movies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movies ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE
  public.users,
  public.user_stats,
  public.user_movies,
  public.movies
FROM anon, authenticated;

-- The backend service_role/secret key is the only intended data-plane access.
-- service_role bypasses RLS; do not put this key in frontend code or client env.
-- No anon/authenticated policies are created intentionally.

-- Optional cleanup, to be reviewed and applied as a separate change only after
-- confirming that no operational process depends on the custom event trigger:
-- REVOKE ALL PRIVILEGES ON FUNCTION public.rls_auto_enable() FROM PUBLIC;
-- DROP EVENT TRIGGER IF EXISTS ensure_rls;
-- DROP FUNCTION IF EXISTS public.rls_auto_enable();

COMMIT;

-- Post-apply checks (run separately, read-only):
-- SELECT relname, relrowsecurity, relforcerowsecurity
-- FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
-- WHERE n.nspname = 'public' AND relname IN ('users','user_stats','user_movies','movies');
-- SELECT * FROM pg_policies WHERE schemaname = 'public';
-- SELECT * FROM information_schema.role_table_grants
-- WHERE table_schema = 'public'
--   AND table_name IN ('users','user_stats','user_movies','movies')
--   AND grantee IN ('anon','authenticated');
