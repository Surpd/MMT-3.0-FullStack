-- Preserve separate movie and TV interactions when TMDB IDs overlap.
-- Existing legacy rows were sometimes written with the default `movie` while
-- the catalog already identified the title as TV. Reconcile from catalog
-- metadata before adding the NOT NULL/composite key constraints.
update public.user_movies um
set media_type = m.media_type
from public.movies m
where m.id = um.movie_id
  and m.media_type in ('movie', 'tv')
  and coalesce(um.media_type, 'movie') <> m.media_type;

update public.user_movies
set media_type = 'movie'
where media_type is null;

alter table public.user_movies
  alter column media_type set default 'movie',
  alter column media_type set not null;

alter table public.user_movies
  drop constraint if exists user_movies_media_type_check;
alter table public.user_movies
  add constraint user_movies_media_type_check check (media_type in ('movie', 'tv'));

alter table public.user_movies
  drop constraint if exists user_movies_pkey;

alter table public.user_movies
  add constraint user_movies_pkey primary key (user_id, movie_id, media_type);

create index if not exists user_movies_user_status_media_idx
  on public.user_movies (user_id, status, media_type);

create index if not exists user_movies_movie_media_idx
  on public.user_movies (movie_id, media_type);
