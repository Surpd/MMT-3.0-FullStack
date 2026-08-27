-- A bounded idempotency marker for frontend retry; this is not an event log.
alter table public.user_movies
  add column if not exists last_action_id text;

alter table public.user_movies
  drop constraint if exists user_movies_last_action_id_length_check;
alter table public.user_movies
  add constraint user_movies_last_action_id_length_check
  check (last_action_id is null or char_length(last_action_id) between 1 and 128);

create index if not exists user_movies_user_action_idx
  on public.user_movies (user_id, last_action_id)
  where last_action_id is not null;
