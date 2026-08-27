-- Derived, bounded taste snapshot. user_movies remains the source of truth.
create table if not exists public.user_taste_profiles (
  user_id bigint primary key references public.users(id) on delete cascade,
  genres_jsonb jsonb not null default '{}'::jsonb,
  keywords_jsonb jsonb not null default '{}'::jsonb,
  directors_jsonb jsonb not null default '{}'::jsonb,
  countries_jsonb jsonb not null default '{}'::jsonb,
  eras_jsonb jsonb not null default '{}'::jsonb,
  movie_modifiers_jsonb jsonb not null default '{}'::jsonb,
  tv_modifiers_jsonb jsonb not null default '{}'::jsonb,
  interaction_count integer not null default 0 check (interaction_count >= 0),
  profile_version integer not null default 0 check (profile_version >= 0),
  updated_at timestamptz not null default now()
);

alter table public.user_taste_profiles enable row level security;
revoke all on public.user_taste_profiles from anon, authenticated;
