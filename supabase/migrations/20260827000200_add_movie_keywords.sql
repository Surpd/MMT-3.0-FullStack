alter table public.movies
  add column if not exists keywords text[];
