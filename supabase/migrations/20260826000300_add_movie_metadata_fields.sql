-- Backward-compatible metadata enrichment fields. Existing user state is untouched.
alter table public.movies
  add column if not exists production_countries text[],
  add column if not exists origin_country text[],
  add column if not exists original_title text,
  add column if not exists original_language text,
  add column if not exists backdrop_url text,
  add column if not exists tmdb_vote_count integer,
  add column if not exists production_companies text[];
