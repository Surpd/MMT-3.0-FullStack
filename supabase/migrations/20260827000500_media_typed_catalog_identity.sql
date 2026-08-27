-- Make the global catalog identity match TMDB's two namespaces.
-- Existing TV child rows are unambiguously TV and receive that type before
-- foreign keys are recreated. No user data is deleted.
update public.movies set media_type = 'movie' where media_type is null;
alter table public.movies
  alter column media_type set default 'movie',
  alter column media_type set not null;

alter table public.tv_seasons add column if not exists media_type text default 'tv';
update public.tv_seasons set media_type = 'tv' where media_type is null;
alter table public.tv_seasons alter column media_type set not null;
alter table public.tv_seasons drop constraint if exists tv_seasons_media_type_check;
alter table public.tv_seasons
  add constraint tv_seasons_media_type_check check (media_type = 'tv');

alter table public.tv_notification_subscriptions add column if not exists media_type text default 'tv';
update public.tv_notification_subscriptions set media_type = 'tv' where media_type is null;
alter table public.tv_notification_subscriptions alter column media_type set not null;
alter table public.tv_notification_subscriptions drop constraint if exists tv_notification_subscriptions_media_type_check;
alter table public.tv_notification_subscriptions
  add constraint tv_notification_subscriptions_media_type_check check (media_type = 'tv');

alter table public.tv_notification_deliveries add column if not exists media_type text default 'tv';
update public.tv_notification_deliveries set media_type = 'tv' where media_type is null;
alter table public.tv_notification_deliveries alter column media_type set not null;
alter table public.tv_notification_deliveries drop constraint if exists tv_notification_deliveries_media_type_check;
alter table public.tv_notification_deliveries
  add constraint tv_notification_deliveries_media_type_check check (media_type = 'tv');

-- Drop dependent foreign keys before replacing the catalog primary key.
alter table public.user_movies drop constraint if exists user_movies_movie_id_fkey;
alter table public.tv_seasons drop constraint if exists tv_seasons_tv_id_fkey;
alter table public.tv_notification_subscriptions drop constraint if exists tv_notification_subscriptions_tv_id_fkey;
alter table public.tv_notification_deliveries drop constraint if exists tv_notification_deliveries_tv_id_fkey;

alter table public.movies drop constraint if exists movies_pkey;
alter table public.movies add constraint movies_pkey primary key (id, media_type);

alter table public.user_movies
  add constraint user_movies_movie_id_fkey
  foreign key (movie_id, media_type) references public.movies (id, media_type);

alter table public.tv_seasons
  add constraint tv_seasons_tv_id_fkey
  foreign key (tv_id, media_type) references public.movies (id, media_type);

alter table public.tv_notification_subscriptions
  add constraint tv_notification_subscriptions_tv_id_fkey
  foreign key (tv_id, media_type) references public.movies (id, media_type);

alter table public.tv_notification_deliveries
  add constraint tv_notification_deliveries_tv_id_fkey
  foreign key (tv_id, media_type) references public.movies (id, media_type);

create index if not exists movies_media_identity_idx on public.movies (id, media_type);
create index if not exists tv_seasons_tv_media_idx on public.tv_seasons (tv_id, media_type);
create index if not exists tv_notification_subscriptions_tv_media_idx
  on public.tv_notification_subscriptions (tv_id, media_type);
create index if not exists tv_notification_deliveries_tv_media_idx
  on public.tv_notification_deliveries (tv_id, media_type);
