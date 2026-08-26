// Backend API client for the swipe deck.
export const API_BASE = "https://mmt-3-0-fullstack.onrender.com";
//export const API_BASE = "http://localhost:8000";

export const TMDB_IMG = "https://image.tmdb.org/t/p/w500";

export type MediaType = "movie" | "tv";
export type ApiMovie = {
  movie_id: number;
  title: string;
  poster_path?: string;
  media_type?: MediaType;
  genre_ids?: number[];
  genre_names?: string[];
  user_rating?: number;
  user_status?: string;
  year?: number | string;
  rating?: number;
  reason?: string;
  overview?: string;
  actors?: string[];
  directors?: string[];
  runtime_mins?: number;
  seasons?: number;
  tv_status?: string;
  number_of_episodes?: number;
  last_air_date?: string;
  next_episode?: string;
  tv_progress?: TvProgress;
};

export type TvEpisode = { season_number?: number; episode_number: number; name?: string; air_date?: string; watched?: boolean };
export type TvSeasonProgress = { season_number: number; name?: string; episode_count: number; available_episode_count: number | null; watched_episode_count: number; loaded?: boolean; episodes: TvEpisode[] };
export type TvProgress = { seasons: TvSeasonProgress[]; watched_episodes: number; available_episodes: number; known_episodes?: number; next_episode?: TvEpisode | null; caught_up: boolean; completed: boolean; state?: "none" | "watchlist" | "watching" | "caught_up" | "completed"; tv_status?: string; next_air_date?: string | null; notification_enabled?: boolean };

export type DeckMovie = {
  movie_id: number;
  title: string;
  poster: string;
  poster_path: string;
  media_type: MediaType;
  genre_ids: number[];
  genre_names: string[];
  user_rating?: number;
  user_status?: string;
  year?: number | string;
  rating?: number;
  reason?: string;
  overview?: string;
  actors?: string[];
  directors?: string[];
  runtime_mins?: number;
  seasons?: number;
  tv_status?: string;
  number_of_episodes?: number;
  last_air_date?: string;
  next_episode?: string;
  tv_progress?: TvProgress;
};

const ENDED_TV_STATUSES = new Set(["Ended", "Canceled", "Завершен"]);

export type TvDisplayMeta = {
  seasonLabel?: string;
  statusLabel?: "Завершен" | "Идет";
  fallbackLabel?: "Сериал";
};

export function getTvDisplayMeta(seasons?: number, tvStatus?: string): TvDisplayMeta {
  const hasSeasons = typeof seasons === "number" && Number.isInteger(seasons) && seasons > 0;
  const hasStatus = typeof tvStatus === "string" && tvStatus.trim().length > 0;
  const meta: TvDisplayMeta = {};

  if (hasSeasons) meta.seasonLabel = `${seasons} сез.`;
  if (hasStatus) meta.statusLabel = ENDED_TV_STATUSES.has(tvStatus!.trim()) ? "Завершен" : "Идет";
  if (!meta.seasonLabel && !meta.statusLabel) meta.fallbackLabel = "Сериал";
  return meta;
}

export function formatTvSeasons(seasons?: number): string {
  return getTvDisplayMeta(seasons).seasonLabel ?? "Сериал";
}

export function formatTvStatus(tvStatus?: string): "Завершен" | "Идет" | undefined {
  return getTvDisplayMeta(undefined, tvStatus).statusLabel;
}

export function formatTvCardMeta(seasons?: number, tvStatus?: string, long = false): string {
  const meta = getTvDisplayMeta(seasons, tvStatus);
  const seasonLabel = long ? meta.seasonLabel?.replace("сез.", "сезонов") : meta.seasonLabel;
  return [seasonLabel, meta.statusLabel].filter(Boolean).join(" · ") || meta.fallbackLabel!;
}

function mapApiMovieToDeck(m: ApiMovie): DeckMovie {
  return {
    movie_id: typeof m.movie_id === "number" ? m.movie_id : (typeof (m as any).id === "number" ? (m as any).id : 0),
    title: m.title ?? "",
    poster: m.poster_path
      ? (m.poster_path.startsWith("http") ? m.poster_path : `${TMDB_IMG}${m.poster_path}`)
      : "",
    poster_path: m.poster_path ?? "",
    media_type: m.media_type === "tv" ? "tv" : "movie",
    genre_ids: Array.isArray(m.genre_ids) ? m.genre_ids : [],
    genre_names: Array.isArray(m.genre_names) ? m.genre_names : [],
    user_rating: typeof m.user_rating === "number" ? m.user_rating : undefined,
    user_status: m.user_status,
    year: m.year,
    rating: typeof m.rating === "number" ? m.rating : (typeof m.user_rating === "number" ? m.user_rating : undefined),
    reason: m.reason,
    overview: m.overview,
    actors: Array.isArray(m.actors) ? m.actors : undefined,
    directors: Array.isArray(m.directors) ? m.directors : undefined,
    runtime_mins: typeof m.runtime_mins === "number" ? m.runtime_mins : undefined,
    seasons: typeof m.seasons === "number" ? m.seasons : undefined,
    tv_status: typeof m.tv_status === "string" ? m.tv_status : undefined,
    number_of_episodes: typeof m.number_of_episodes === "number" ? m.number_of_episodes : undefined,
    last_air_date: m.last_air_date,
    next_episode: m.next_episode,
    tv_progress: m.tv_progress,
  };
}

export type SwipeAction = "liked" | "archive" | "watchlist";
export type LibraryStatus = "liked" | "watchlist" | "archive";

export type LibraryItem = DeckMovie;

export type UserStats = {
  points: number;
  best_streak: number;
  current_streak: number;
  level?: number;
  title?: string;
};

// ЕДИНСТВЕННЫЙ И ПРАВИЛЬНЫЙ ОПРЕДЕЛИТЕЛЬ ID
export function getUserId(): number {
  const tg = typeof window !== "undefined" ? (window as any).Telegram?.WebApp : null;
  const telegramUserId = tg?.initDataUnsafe?.user?.id;
  if (typeof telegramUserId === "number" && telegramUserId > 0) return telegramUserId;

  const devUserId = import.meta.env.DEV ? Number(import.meta.env.VITE_DEV_USER_ID) : NaN;
  if (Number.isSafeInteger(devUserId) && devUserId > 0) return devUserId;
  throw new Error("Telegram user identity is unavailable");
}

export type QuizData = {
  question: string;
  options: string[];
  quiz_id: string;
};

export function getInitData(): string {
  const tg = typeof window !== "undefined" ? (window as any).Telegram?.WebApp : null;
  return tg?.initData || "";
}

// Вспомогательная функция для сборки заголовков
export function getAuthHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    "Authorization": `tma ${getInitData()}`
  };
}

export async function fetchStats(): Promise<UserStats | null> {
  try {
    const res = await fetch(`${API_BASE}/api/stats?user_id=${getUserId()}`, {
      headers: getAuthHeaders(),
    });
    const data = (await res.json()) as { ok?: boolean; stats?: UserStats; level?: number; title?: string };
    if (!data.ok || !data.stats) return null;
    return { ...data.stats, level: data.level, title: data.title };
  } catch (e) {
    return null;
  }
}

export async function fetchQuizQuestion(): Promise<QuizData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/quiz`, {
      headers: getAuthHeaders(),
    });
    const data = (await res.json()) as { ok?: boolean; quiz?: QuizData };
    if (!res.ok || !data?.ok || !data.quiz) return null;

    const question = typeof data.quiz.question === "string" ? data.quiz.question : "";
    const options = Array.isArray(data.quiz.options) ? data.quiz.options.filter((option): option is string => typeof option === "string") : [];
    const quizId = typeof data.quiz.quiz_id === "string" ? data.quiz.quiz_id : "";

    if (!question || options.length === 0 || !quizId) return null;

    return { question, options, quiz_id: quizId };
  } catch (e) {
    return null;
  }
}

export async function postQuizAnswer(
  quizId: string,
  answer: string,
): Promise<{ message: string; stats: UserStats; is_correct: boolean; correct_answer: string } | null> {
  try {
    const res = await fetch(`${API_BASE}/api/quiz/answer`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ user_id: getUserId(), quiz_id: quizId, answer }),
    });
    const data = (await res.json()) as { ok?: boolean; message?: string; stats?: UserStats; level?: number; title?: string; is_correct?: boolean; correct_answer?: string };
    if (!data.ok || !data.message || !data.stats || typeof data.is_correct !== "boolean" || typeof data.correct_answer !== "string") return null;
    return { message: data.message, stats: { ...data.stats, level: data.level, title: data.title }, is_correct: data.is_correct, correct_answer: data.correct_answer };
  } catch (e) {
    return null;
  }
}

export async function fetchLibrary(
  status: LibraryStatus,
  page: number = 1,
): Promise<LibraryItem[]> {
  const userId = getUserId();
  const url = `${API_BASE}/api/library?user_id=${userId}&status=${status}&page=${page}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`library HTTP ${res.status}`);
  const data = (await res.json()) as { ok?: boolean; movies?: ApiMovie[] };
  const movies = Array.isArray(data?.movies) ? data.movies : [];
  return movies.map((m) => ({
    ...mapApiMovieToDeck(m),
    user_rating: typeof m.user_rating === "number" ? m.user_rating : 0,
    rating: typeof m.rating === "number" ? m.rating : undefined,
  }));
}

export async function searchMovies(query: string, userId: number): Promise<DeckMovie[]> {
  const url = `${API_BASE}/api/search?user_id=${userId}&q=${encodeURIComponent(query)}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`search HTTP ${res.status}`);
  const data = (await res.json()) as { ok?: boolean; movies?: ApiMovie[] };
  const movies = Array.isArray(data?.movies) ? data.movies : [];
  return movies.map((m) => ({
    ...mapApiMovieToDeck(m),
    user_rating: typeof m.user_rating === "number" ? m.user_rating : 0,
  }));
}

export async function fetchMovieDetails(movieId: number, mediaType: MediaType = "movie"): Promise<DeckMovie | null> {
  try {
    const res = await fetch(`${API_BASE}/api/movie?movie_id=${movieId}&user_id=${getUserId()}&media_type=${mediaType}`, {
      headers: getAuthHeaders(),
    });
    const data = (await res.json()) as { ok?: boolean; movie?: ApiMovie; user_status?: string; user_rating?: number; tv_progress?: TvProgress };
    if (!data.ok || !data.movie) return null;
    const m = data.movie;
    return {
      ...mapApiMovieToDeck(m),
      movie_id: typeof m.movie_id === "number" ? m.movie_id : movieId,
      media_type: m.media_type === "tv" ? "tv" : mediaType,
      user_rating: data.user_rating || 0,
      user_status: (data.user_status ?? m.user_status) && (data.user_status ?? m.user_status) !== "none" ? (data.user_status ?? m.user_status) : undefined,
      tv_progress: data.tv_progress,
    };
  } catch (e) {
    return null;
  }
}

export type FetchMoviesResult = {
  movies: DeckMovie[];
  next_cursor: number | null;
};

export type RecommendationParams = {
  target_type?: string;
  min_year?: number;
  min_rating?: number;
};

export async function fetchRecommendations(
  userId: number,
  skip: number,
  params?: RecommendationParams,
): Promise<FetchMoviesResult> {
  const searchParams = new URLSearchParams({
    user_id: String(userId),
    skip: String(skip),
  });
  if (params?.target_type) searchParams.set("target_type", params.target_type);
  if (params?.min_year != null) searchParams.set("min_year", String(params.min_year));
  if (params?.min_rating != null) searchParams.set("min_rating", String(params.min_rating));

  const res = await fetch(`${API_BASE}/api/recommendations?${searchParams}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`recommendations HTTP ${res.status}`);
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
    user_status: m.user_status,
    year: m.year,
    rating: typeof m.rating === "number" ? m.rating : (typeof m.user_rating === "number" ? m.user_rating : undefined),
    reason: m.reason,
    overview: m.overview,
    actors: Array.isArray(m.actors) ? m.actors : undefined,
    directors: Array.isArray(m.directors) ? m.directors : undefined,
    runtime_mins: typeof m.runtime_mins === "number" ? m.runtime_mins : undefined,
  }));
  return {
    movies,
    next_cursor: typeof data.next_cursor === "number" ? data.next_cursor : null,
  };
}

export async function fetchMovies(cursor: number = 0): Promise<FetchMoviesResult> {
  const userId = getUserId();
  const url = `${API_BASE}/api/movies?user_id=${userId}&cursor=${cursor}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
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
  const movies: DeckMovie[] = data.movies.map((m) => mapApiMovieToDeck(m));
  return {
    movies,
    next_cursor:
      typeof data.next_cursor === "number" ? data.next_cursor : null,
  };
}

export async function postSwipe(movie: DeckMovie, action: SwipeAction): Promise<boolean> {
  const payload = {
    user_id: getUserId(),
    movie_id: movie.movie_id,
    action,
    media_type: movie.media_type,
    genre_ids: movie.genre_ids,
  };
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(`${API_BASE}/api/swipe`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
        keepalive: true,
      });
      if (response.ok) return true;
    } catch (e) {
      if (attempt === 1) console.warn("[api.swipe] failed", e);
    }
    if (attempt === 0) await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

export async function rateMovie(movieId: number, mediaType: MediaType, rating: number): Promise<void> {
  await fetch(`${API_BASE}/api/rate`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ user_id: getUserId(), movie_id: movieId, media_type: mediaType, rating }),
  }).catch((e) => console.warn("[api.rate] failed", e));
}

export async function fetchSearchTags(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/api/search/tags?user_id=${getUserId()}`, {
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    return data.tags || [];
  } catch (e) {
    return [];
  }
}
