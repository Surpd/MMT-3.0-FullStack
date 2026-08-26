-- Additive TV tracking schema. Existing movie/user data is preserved.
alter table public.movies
  add column if not exists number_of_episodes integer,
  add column if not exists last_air_date date,
  add column if not exists metadata_updated_at timestamptz;

create table if not exists public.tv_seasons (
  tv_id bigint not null references public.movies(id) on delete cascade,
  season_number integer not null,
  name text,
  episode_count integer not null default 0,
  air_date date,
  poster_path text,
  metadata_updated_at timestamptz not null default now(),
  primary key (tv_id, season_number),
  check (season_number >= 0),
  check (episode_count >= 0)
);

create table if not exists public.tv_episodes (
  tv_id bigint not null,
  season_number integer not null,
  episode_number integer not null,
  name text,
  overview text,
  air_date date,
  runtime_mins smallint,
  still_path text,
  metadata_updated_at timestamptz not null default now(),
  primary key (tv_id, season_number, episode_number),
  foreign key (tv_id, season_number) references public.tv_seasons(tv_id, season_number) on delete cascade,
  check (season_number >= 0),
  check (episode_number > 0)
);

create table if not exists public.user_episode_progress (
  user_id bigint not null references public.users(id) on delete cascade,
  tv_id bigint not null,
  season_number integer not null,
  episode_number integer not null,
  watched_at timestamptz not null default now(),
  primary key (user_id, tv_id, season_number, episode_number),
  foreign key (tv_id, season_number, episode_number)
    references public.tv_episodes(tv_id, season_number, episode_number) on delete cascade
);

create table if not exists public.tv_notification_subscriptions (
  user_id bigint not null references public.users(id) on delete cascade,
  tv_id bigint not null references public.movies(id) on delete cascade,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, tv_id)
);

create table if not exists public.tv_notification_deliveries (
  user_id bigint not null references public.users(id) on delete cascade,
  tv_id bigint not null references public.movies(id) on delete cascade,
  season_number integer not null,
  episode_number integer not null,
  sent_at timestamptz not null default now(),
  primary key (user_id, tv_id, season_number, episode_number)
);

create index if not exists tv_episodes_air_date_idx
  on public.tv_episodes (tv_id, air_date);
create index if not exists user_episode_progress_tv_idx
  on public.user_episode_progress (user_id, tv_id, season_number, episode_number);
create index if not exists tv_notification_subscriptions_enabled_idx
  on public.tv_notification_subscriptions (tv_id)
  where enabled;

alter table public.tv_seasons enable row level security;
alter table public.tv_episodes enable row level security;
alter table public.user_episode_progress enable row level security;
alter table public.tv_notification_subscriptions enable row level security;
alter table public.tv_notification_deliveries enable row level security;

revoke all on public.tv_seasons, public.tv_episodes, public.user_episode_progress,
  public.tv_notification_subscriptions, public.tv_notification_deliveries
  from anon, authenticated;
