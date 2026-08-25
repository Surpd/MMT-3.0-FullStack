# Supabase baseline checklist

Статический audit не нашёл в репозитории SQL schema, migrations или доступного read-only metadata tooling. Production Supabase не трогался. Перед созданием baseline нужно выполнить вручную в контролируемом окружении с read-only доступом к metadata.

## Required evidence

- project/ref and environment name, without secrets;
- tables: `users`, `profiles`, `user_stats`, `movies`, `user_movies`;
- columns, PostgreSQL types, nullability and defaults;
- primary keys;
- foreign keys, especially `user_movies.user_id` and `user_movies.movie_id`;
- unique constraints, especially `(user_id, movie_id)`;
- indexes and their definitions;
- RLS enabled state for every application table;
- SELECT/INSERT/UPDATE/DELETE policies and their ownership predicates;
- functions and triggers affecting users, stats, movies or user_movies;
- grants/roles relevant to the application key type.

## Safe read-only procedure

1. Confirm the target project and environment out-of-band.
2. Use Supabase dashboard metadata export or a read-only PostgreSQL connection; do not use application write credentials for discovery.
3. Export schema-only metadata, excluding data and secrets.
4. Capture the output as a versioned baseline under a separately reviewed database directory; do not call it a migration.
5. Compare the baseline with the code assumptions in [DATA_MODEL.md](DATA_MODEL.md).
6. Review discrepancies before proposing any migration or RLS change.

## SQL metadata queries

Run only against the intended project with a read-only role. Replace `public` only if the project uses another schema.

```sql
select table_name, column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public'
order by table_name, ordinal_position;

select tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name,
       ccu.table_name as foreign_table_name, ccu.column_name as foreign_column_name
from information_schema.table_constraints tc
left join information_schema.key_column_usage kcu
  on tc.constraint_name = kcu.constraint_name and tc.table_schema = kcu.table_schema
left join information_schema.constraint_column_usage ccu
  on tc.constraint_name = ccu.constraint_name and tc.table_schema = ccu.table_schema
where tc.table_schema = 'public'
order by tc.table_name, tc.constraint_name, kcu.ordinal_position;

select schemaname, tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
order by tablename, indexname;

select schemaname, tablename, rowsecurity, forcerowsecurity
from pg_tables
where schemaname = 'public'
order by tablename;

select schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
from pg_policies
where schemaname = 'public'
order by tablename, policyname;

select n.nspname as schema_name, p.proname as function_name,
       pg_get_functiondef(p.oid) as definition
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public';

select event_object_schema, event_object_table, trigger_name,
       action_statement, action_timing, event_manipulation
from information_schema.triggers
where event_object_schema = 'public'
order by event_object_table, trigger_name;
```

## Stop conditions

Stop and report a blocker if the project/ref cannot be verified, only write-capable credentials are available, or the export would include production data/secrets. No production migrations, policy changes, schema changes or data writes are authorized by this checklist.
