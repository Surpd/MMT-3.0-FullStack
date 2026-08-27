import assert from "node:assert/strict";
import test from "node:test";
import { fetchMovieDetails, primeMovieDetails, type DeckMovie } from "./api.ts";

const baseMovie = (movieId: number, mediaType: "movie" | "tv" = "movie"): DeckMovie => ({
  movie_id: movieId,
  title: `${mediaType}-${movieId}`,
  poster: "/poster.jpg",
  poster_path: "/poster.jpg",
  media_type: mediaType,
  genre_ids: [],
  genre_names: [],
  overview: "Cached overview",
});

const originalFetch = globalThis.fetch;

test.afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("library snapshot primes detail cache without a duplicate request", async () => {
  globalThis.window = {
    Telegram: { WebApp: { initDataUnsafe: { user: { id: 7 } }, initData: "test" } },
  } as unknown as Window & typeof globalThis;
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    throw new Error("cache should have satisfied the request");
  }) as typeof fetch;

  const movie = baseMovie(9101);
  primeMovieDetails(movie);
  const result = await fetchMovieDetails(movie.movie_id, movie.media_type);

  assert.equal(result?.title, movie.title);
  assert.equal(calls, 0);
});

test("in-flight detail requests are shared for a sparse library snapshot", async () => {
  globalThis.window = {
    Telegram: { WebApp: { initDataUnsafe: { user: { id: 8 } }, initData: "test" } },
  } as unknown as Window & typeof globalThis;
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 5));
    return {
      ok: true,
      json: async () => ({
        ok: true,
        movie: {
          movie_id: 9102,
          title: "Hydrated",
          poster_path: "/poster.jpg",
          media_type: "movie",
          overview: "Loaded",
          actors: ["Actor"],
        },
      }),
    } as Response;
  }) as typeof fetch;

  const sparse = { ...baseMovie(9102), overview: undefined, genre_names: [] };
  primeMovieDetails(sparse);
  const [first, second] = await Promise.all([
    fetchMovieDetails(9102, "movie"),
    fetchMovieDetails(9102, "movie"),
  ]);

  assert.equal(calls, 1);
  assert.equal(first?.title, "Hydrated");
  assert.equal(second?.title, "Hydrated");
});

test("movie and TV detail cache entries do not collide on numeric IDs", async () => {
  globalThis.window = {
    Telegram: { WebApp: { initDataUnsafe: { user: { id: 9 } }, initData: "test" } },
  } as unknown as Window & typeof globalThis;
  globalThis.fetch = (async () => {
    throw new Error("typed snapshots should have satisfied the requests");
  }) as typeof fetch;

  primeMovieDetails(baseMovie(9103, "movie"));
  primeMovieDetails(baseMovie(9103, "tv"));
  const [movie, tv] = await Promise.all([
    fetchMovieDetails(9103, "movie"),
    fetchMovieDetails(9103, "tv"),
  ]);

  assert.equal(movie?.media_type, "movie");
  assert.equal(tv?.media_type, "tv");
});
