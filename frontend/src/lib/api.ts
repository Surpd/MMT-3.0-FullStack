// Backend API client for the swipe deck.
export const API_BASE = "http://localhost:10000";
export const TMDB_IMG = "https://image.tmdb.org/t/p/w500";

export type ApiMovie = {
  movie_id: number;
  title: string;
  poster_path?: string;
  media_type?: string;
  genre_ids?: number[];
  genre_names?: string[];
  user_rating?: number;
  year?: number | string;
  reason?: string;
  overview?: string;
  actors?: string[];
  directors?: string[];
  runtime_mins?: number;
};

export type DeckMovie = {
  movie_id: number;
  title: string;
  poster: string;
  poster_path: string;
  media_type: string;
  genre_ids: number[];
  genre_names: string[];
  user_rating?: number;
  year?: number | string;
  reason?: string;
  overview?: string;
  actors?: string[];
  directors?: string[];
  runtime_mins?: number;
};

export type SwipeAction = "liked" | "archive" | "watchlist";
export type LibraryStatus = "liked" | "watchlist" | "archive";

export type LibraryItem = DeckMovie;

// ЕДИНСТВЕННЫЙ И ПРАВИЛЬНЫЙ ОПРЕДЕЛИТЕЛЬ ID
export function getUserId(): number {
  const tg = typeof window !== "undefined" ? (window as any).Telegram?.WebApp : null;
  return tg?.initDataUnsafe?.user?.id || 429426063;
}

export async function fetchLibrary(
  status: LibraryStatus,
  page: number = 1,
): Promise<LibraryItem[]> {
  const userId = getUserId();
  const url = `${API_BASE}/api/library?user_id=${userId}&status=${status}&page=${page}`;
  const res = await fetch(url, {
    headers: { "ngrok-skip-browser-warning": "true" },
  });
  if (!res.ok) throw new Error(`library HTTP ${res.status}`);
  const data = (await res.json()) as { ok?: boolean; movies?: ApiMovie[] };
  const movies = Array.isArray(data?.movies) ? data.movies : [];
  return movies.map((m) => ({
    movie_id: typeof m.movie_id === "number" ? m.movie_id : (typeof (m as any).id === "number" ? (m as any).id : 0),
    title: m.title ?? "",
    poster: m.poster_path
      ? (m.poster_path.startsWith("http") ? m.poster_path : `${TMDB_IMG}${m.poster_path}`)
      : "",
    poster_path: m.poster_path ?? "",
    media_type: m.media_type ?? "movie",
    genre_ids: Array.isArray(m.genre_ids) ? m.genre_ids : [],
    genre_names: Array.isArray(m.genre_names) ? m.genre_names : [],
    user_rating: typeof m.user_rating === "number" ? m.user_rating : undefined,
    year: m.year,
    reason: m.reason,
    overview: m.overview,
    actors: Array.isArray(m.actors) ? m.actors : undefined,
    directors: Array.isArray(m.directors) ? m.directors : undefined,
    runtime_mins: typeof m.runtime_mins === "number" ? m.runtime_mins : undefined,
  }));
}

export type FetchMoviesResult = {
  movies: DeckMovie[];
  next_cursor: number | null;
};

export async function fetchMovies(cursor: number = 0): Promise<FetchMoviesResult> {
  const userId = getUserId();
  const url = `${API_BASE}/api/movies?user_id=${userId}&cursor=${cursor}`;
  const res = await fetch(url, {
    headers: { "ngrok-skip-browser-warning": "true" },
  });
  if (!res.ok) throw new Error(`movies HTTP ${res.status}`);
  const data = (await res.json()) as {
    ok: boolean;
    movies: ApiMovie[];
    next_cursor?: number | null;
  };
  if (!data?.ok || !Array.isArray(data.movies)) {
    return { movies: [], next_cursor: null };
  }
  const movies: DeckMovie[] = data.movies.map((m) => ({
    movie_id: typeof m.movie_id === "number" ? m.movie_id : (typeof (m as any).id === "number" ? (m as any).id : 0),
    title: m.title ?? "",
    poster: m.poster_path
      ? (m.poster_path.startsWith("http") ? m.poster_path : `${TMDB_IMG}${m.poster_path}`)
      : "",
    poster_path: m.poster_path ?? "",
    media_type: m.media_type ?? "movie",
    genre_ids: Array.isArray(m.genre_ids) ? m.genre_ids : [],
    genre_names: Array.isArray(m.genre_names) ? m.genre_names : [],
    user_rating: typeof m.user_rating === "number" ? m.user_rating : undefined,
    year: m.year,
    reason: m.reason,
    overview: m.overview,
    actors: Array.isArray(m.actors) ? m.actors : undefined,
    directors: Array.isArray(m.directors) ? m.directors : undefined,
    runtime_mins: typeof m.runtime_mins === "number" ? m.runtime_mins : undefined,
  }));
  return {
    movies,
    next_cursor:
      typeof data.next_cursor === "number" ? data.next_cursor : null,
  };
}

export function postSwipe(movie: DeckMovie, action: SwipeAction): void {
  const payload = {
    user_id: getUserId(),
    movie_id: movie.movie_id,
    action,
    media_type: movie.media_type,
    genre_ids: movie.genre_ids,
  };
  fetch(`${API_BASE}/api/swipe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch((e) => {
    console.warn("[api.swipe] failed", e);
  });
}
