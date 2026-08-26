alter table public.movies
  add constraint movies_media_type_check check (media_type in ('movie', 'tv')),
  add constraint movies_rating_numeric_check check (rating_numeric is null or (rating_numeric >= 0 and rating_numeric <= 10));

alter table public.user_movies
  add constraint user_movies_rating_check check (rating is null or (rating >= 1 and rating <= 5));
