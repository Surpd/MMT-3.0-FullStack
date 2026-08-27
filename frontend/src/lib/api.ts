// Backend API client for the swipe deck.
export const API_BASE = "https://mmt-3-0-fullstack.onrender.com";
//export const API_BASE = "http://localhost:8000";

export const TMDB_IMG = "https://image.tmdb.org/t/p/w500";

export type MediaType = "movie" | "tv";
export type ApiMovie = {
  id?: number;
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

export type TvEpisode = {
  season_number?: number;
  episode_number: number;
  name?: string;
  air_date?: string;
  watched?: boolean;
};
export type TvSeasonProgress = {
  season_number: number;
  name?: string;
  episode_count: number;
  available_episode_count: number | null;
  watched_episode_count: number;
  loaded?: boolean;
  episodes: TvEpisode[];
};
export type TvProgress = {
  seasons: TvSeasonProgress[];
  watched_episodes: number;
  available_episodes: number;
  known_episodes?: number;
  next_episode?: TvEpisode | null;
  caught_up: boolean;
  completed: boolean;
  state?: "none" | "watchlist" | "watching" | "caught_up" | "completed";
  tv_status?: string;
  next_air_date?: string | null;
  notification_enabled?: boolean;
  metadata_complete?: boolean;
};

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

function formatTvSeasonCount(seasons: number): string {
  const mod10 = seasons % 10;
  const mod100 = seasons % 100;
  const word =
    mod10 === 1 && mod100 !== 11
      ? "сезон"
      : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
        ? "сезона"
        : "сезонов";
  return `${seasons} ${word}`;
}

export function getTvDisplayMeta(seasons?: number, tvStatus?: string): TvDisplayMeta {
  const hasSeasons = typeof seasons === "number" && Number.isInteger(seasons) && seasons > 0;
  const hasStatus = typeof tvStatus === "string" && tvStatus.trim().length > 0;
  const meta: TvDisplayMeta = {};

  if (hasSeasons) meta.seasonLabel = formatTvSeasonCount(seasons);
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

export function formatTvCardMeta(seasons?: number, tvStatus?: string): string {
  const meta = getTvDisplayMeta(seasons, tvStatus);
  return [meta.seasonLabel, meta.statusLabel].filter(Boolean).join(" · ") || meta.fallbackLabel!;
}

function mapApiMovieToDeck(m: ApiMovie): DeckMovie {
  return {
    movie_id: typeof m.movie_id === "number" ? m.movie_id : typeof m.id === "number" ? m.id : 0,
    title: m.title ?? "",
    poster: m.poster_path
      ? m.poster_path.startsWith("http")
        ? m.poster_path
        : `${TMDB_IMG}${m.poster_path}`
      : "",
    poster_path: m.poster_path ?? "",
    media_type: m.media_type === "tv" ? "tv" : "movie",
    genre_ids: Array.isArray(m.genre_ids) ? m.genre_ids : [],
    genre_names: Array.isArray(m.genre_names) ? m.genre_names : [],
    user_rating: typeof m.user_rating === "number" ? m.user_rating : undefined,
    user_status: m.user_status,
    year: m.year,
    rating:
      typeof m.rating === "number"
        ? m.rating
        : typeof m.user_rating === "number"
          ? m.user_rating
          : undefined,
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

export type TasteSummary = {
  taste_source?: "user_taste_profiles";
  interaction_count?: number;
  profile_version?: number;
  maturity?: "empty" | "early" | "forming" | "mature";
  maturity_label?: string;
  confidence?: number;
  genres: Array<{ name: string; share: number }>;
  keywords: Array<{ name: string; share: number }>;
  movie_vs_series: { movies: number; series: number; total: number };
  directors: Array<{ name: string; count?: number; share?: number; rating?: number | null }>;
  actors: Array<{ name: string; count: number }>;
  eras: Array<{ name: string; share: number }>;
  countries: Array<{ name: string; share: number }>;
  country_coverage: { known_titles: number; total_titles: number; coverage_percent?: number };
};

export async function fetchTasteSummary(): Promise<TasteSummary | null> {
  try {
    const res = await fetch(`${API_BASE}/api/profile/taste?user_id=${getUserId()}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { ok?: boolean } & Partial<TasteSummary>;
    if (
      !data.ok ||
      !Array.isArray(data.genres) ||
      !Array.isArray(data.keywords) ||
      !data.movie_vs_series
    )
      return null;
    return data as TasteSummary;
  } catch {
    return null;
  }
}

// ЕДИНСТВЕННЫЙ И ПРАВИЛЬНЫЙ ОПРЕДЕЛИТЕЛЬ ID
export function getUserId(): number {
  const tg =
    typeof window !== "undefined"
      ? (
          window as Window & {
            Telegram?: { WebApp?: { initDataUnsafe?: { user?: { id?: number } } } };
          }
        ).Telegram?.WebApp
      : null;
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
  const tg =
    typeof window !== "undefined"
      ? (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp
      : null;
  return tg?.initData || "";
}

// Вспомогательная функция для сборки заголовков
export function getAuthHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    Authorization: `tma ${getInitData()}`,
  };
}

export async function fetchStats(): Promise<UserStats | null> {
  try {
    const res = await fetch(`${API_BASE}/api/stats?user_id=${getUserId()}`, {
      headers: getAuthHeaders(),
    });
    const data = (await res.json()) as {
      ok?: boolean;
      stats?: UserStats;
      level?: number;
      title?: string;
    };
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
    const options = Array.isArray(data.quiz.options)
      ? data.quiz.options.filter((option): option is string => typeof option === "string")
      : [];
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
): Promise<{
  message: string;
  stats: UserStats;
  is_correct: boolean;
  correct_answer: string;
} | null> {
  try {
    const res = await fetch(`${API_BASE}/api/quiz/answer`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ user_id: getUserId(), quiz_id: quizId, answer }),
    });
    const data = (await res.json()) as {
      ok?: boolean;
      message?: string;
      stats?: UserStats;
      level?: number;
      title?: string;
      is_correct?: boolean;
      correct_answer?: string;
    };
    if (
      !data.ok ||
      !data.message ||
      !data.stats ||
      typeof data.is_correct !== "boolean" ||
      typeof data.correct_answer !== "string"
    )
      return null;
    return {
      message: data.message,
      stats: { ...data.stats, level: data.level, title: data.title },
      is_correct: data.is_correct,
      correct_answer: data.correct_answer,
    };
  } catch (e) {
    return null;
  }
}

const LIBRARY_PAGE_SIZE = 100;
const LIBRARY_CACHE_TTL_MS = 60 * 1000;
type LibraryUpdateListener = (items: LibraryItem[], total: number, complete: boolean) => void;
type LibraryCacheEntry = {
  status: LibraryStatus;
  items: LibraryItem[];
  total: number;
  nextPage: number;
  loadedPages: Set<number>;
  complete: boolean;
  expiresAt: number;
  loading?: Promise<LibraryItem[]>;
  loadingAll?: boolean;
  listeners: Set<LibraryUpdateListener>;
};

const librarySessionCache = new Map<string, LibraryCacheEntry>();

function libraryCacheKey(userId: number, status: LibraryStatus): string {
  return `${userId}:${status}`;
}

function libraryItemKey(item: Pick<LibraryItem, "movie_id" | "media_type">): string {
  return `${item.media_type}:${item.movie_id}`;
}

function notifyLibraryListeners(entry: LibraryCacheEntry) {
  const snapshot = [...entry.items];
  for (const listener of entry.listeners) {
    try {
      listener(snapshot, entry.total, entry.complete);
    } catch {
      // A view subscriber must not break the shared loader.
    }
  }
}

function mergeLibraryItems(existing: LibraryItem[], incoming: LibraryItem[]): LibraryItem[] {
  const seen = new Set(existing.map(libraryItemKey));
  return existing.concat(incoming.filter((item) => !seen.has(libraryItemKey(item))));
}

async function fetchLibraryPage(
  status: LibraryStatus,
  page: number,
): Promise<{ items: LibraryItem[]; total: number }> {
  const url = `${API_BASE}/api/library?user_id=${getUserId()}&status=${status}&page=${page}`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`library HTTP ${res.status}`);
  const data = (await res.json()) as { ok?: boolean; movies?: ApiMovie[]; total?: number };
  const movies = Array.isArray(data?.movies) ? data.movies : [];
  return {
    items: movies.map((m) => ({
      ...mapApiMovieToDeck(m),
      user_rating: typeof m.user_rating === "number" ? m.user_rating : 0,
      rating: typeof m.rating === "number" ? m.rating : undefined,
    })),
    total: typeof data.total === "number" ? data.total : Number.POSITIVE_INFINITY,
  };
}

function pageCompletes(entry: LibraryCacheEntry, pageSize: number): boolean {
  return (
    pageSize === 0 ||
    (Number.isFinite(entry.total) && entry.items.length >= entry.total) ||
    (!Number.isFinite(entry.total) && pageSize < LIBRARY_PAGE_SIZE)
  );
}

async function loadLibraryEntry(
  entry: LibraryCacheEntry,
  startPage: number,
  loadAll: boolean,
): Promise<LibraryItem[]> {
  if (entry.loading) {
    if (!loadAll || entry.loadingAll) return entry.loading;
    await entry.loading;
    return loadLibraryEntry(entry, startPage, true);
  }

  const loading = (async () => {
    let page = entry.nextPage || startPage;
    if (!entry.loadedPages.has(startPage)) {
      const first = await fetchLibraryPage(entry.status, startPage);
      entry.items = startPage === 1 ? first.items : mergeLibraryItems(entry.items, first.items);
      entry.total = first.total;
      entry.loadedPages.add(startPage);
      entry.nextPage = startPage + 1;
      entry.complete = pageCompletes(entry, first.items.length);
      notifyLibraryListeners(entry);
      page = entry.nextPage;
    }

    if (!loadAll) return [...entry.items];

    while (!entry.complete && page <= 1000) {
      if (entry.loadedPages.has(page)) {
        page += 1;
        continue;
      }
      const next = await fetchLibraryPage(entry.status, page);
      entry.items = mergeLibraryItems(entry.items, next.items);
      if (Number.isFinite(next.total)) entry.total = next.total;
      entry.loadedPages.add(page);
      entry.nextPage = page + 1;
      entry.complete = pageCompletes(entry, next.items.length);
      notifyLibraryListeners(entry);
      page += 1;
    }
    entry.expiresAt = Date.now() + LIBRARY_CACHE_TTL_MS;
    return [...entry.items];
  })().finally(() => {
    entry.loading = undefined;
    entry.loadingAll = undefined;
  });
  entry.loading = loading;
  entry.loadingAll = loadAll;
  return loading;
}

export function getCachedLibrary(status: LibraryStatus): LibraryItem[] | null {
  const entry = librarySessionCache.get(libraryCacheKey(getUserId(), status));
  return entry ? [...entry.items] : null;
}

export function patchLibraryCache(movie: LibraryItem, statusChanged = false): void {
  const key = libraryItemKey(movie);
  const nextStatus = movie.user_status as LibraryStatus | undefined;
  for (const entry of librarySessionCache.values()) {
    const index = entry.items.findIndex((item) => libraryItemKey(item) === key);
    if (statusChanged) {
      entry.items = entry.items.filter((item) => libraryItemKey(item) !== key);
      if (entry.status === nextStatus) entry.items.unshift(movie);
    } else if (index >= 0) {
      entry.items = entry.items.map((item, itemIndex) => (itemIndex === index ? movie : item));
    } else {
      continue;
    }
    notifyLibraryListeners(entry);
  }
}

export function patchLibraryRating(movieId: number, mediaType: MediaType, rating: number): void {
  const key = `${mediaType}:${movieId}`;
  for (const entry of librarySessionCache.values()) {
    const index = entry.items.findIndex((item) => libraryItemKey(item) === key);
    if (index < 0) continue;
    entry.items = entry.items.map((item, itemIndex) =>
      itemIndex === index ? { ...item, user_rating: rating } : item,
    );
    notifyLibraryListeners(entry);
  }
}

export function patchLibraryTvProgress(tvId: number, progress: TvProgress): void {
  const key = `tv:${tvId}`;
  for (const entry of librarySessionCache.values()) {
    const index = entry.items.findIndex((item) => libraryItemKey(item) === key);
    if (index < 0) continue;
    entry.items = entry.items.map((item, itemIndex) =>
      itemIndex === index ? { ...item, tv_progress: progress } : item,
    );
    notifyLibraryListeners(entry);
  }
}

export async function fetchLibrary(
  status: LibraryStatus,
  page: number = 1,
  options: { onUpdate?: LibraryUpdateListener; loadAll?: boolean } = {},
): Promise<LibraryItem[]> {
  const userId = getUserId();
  const key = libraryCacheKey(userId, status);
  let entry = librarySessionCache.get(key);
  if (!entry) {
    entry = {
      status,
      items: [],
      total: Number.POSITIVE_INFINITY,
      nextPage: page,
      loadedPages: new Set<number>(),
      complete: false,
      expiresAt: 0,
      listeners: new Set<LibraryUpdateListener>(),
    };
    librarySessionCache.set(key, entry);
  }

  const isFresh = entry.complete && entry.expiresAt > Date.now();
  if ((entry.items.length > 0 || entry.complete) && options.onUpdate) {
    options.onUpdate([...entry.items], entry.total, isFresh && entry.complete);
  }

  if (isFresh) return [...entry.items];

  if (entry.expiresAt > 0 && !entry.loading) {
    entry.loadedPages.clear();
    entry.nextPage = page;
    entry.complete = false;
    entry.expiresAt = 0;
  }

  if (options.onUpdate) entry.listeners.add(options.onUpdate);
  try {
    return await loadLibraryEntry(entry, page, options.loadAll ?? true);
  } finally {
    if (options.onUpdate) entry.listeners.delete(options.onUpdate);
  }
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

const DETAIL_CACHE_TTL_MS = 5 * 60 * 1000;
type MovieDetailsCacheEntry = { movie: DeckMovie; expiresAt: number };
const movieDetailsCache = new Map<string, MovieDetailsCacheEntry>();
const movieDetailsInFlight = new Map<string, Promise<DeckMovie | null>>();

function hasUsefulDetails(movie: DeckMovie): boolean {
  return Boolean(
    movie.overview?.trim() ||
    movie.actors?.length ||
    movie.directors?.length ||
    movie.runtime_mins ||
    (movie.media_type === "tv" && movie.seasons),
  );
}

function mergeDefinedMovie(base: DeckMovie | undefined, next: DeckMovie): DeckMovie {
  const merged = { ...(base ?? {}) } as DeckMovie;
  for (const [key, value] of Object.entries(next)) {
    if (value !== undefined) (merged as Record<string, unknown>)[key] = value;
  }
  return merged;
}

export function primeMovieDetails(movie: DeckMovie): void {
  const key = `${movie.media_type}:${movie.movie_id}`;
  const current = movieDetailsCache.get(key);
  const merged = mergeDefinedMovie(current?.movie, movie);
  const expiresAt =
    current && hasUsefulDetails(current.movie)
      ? current.expiresAt
      : Date.now() + DETAIL_CACHE_TTL_MS;
  movieDetailsCache.set(key, { movie: merged, expiresAt });
}

export async function fetchMovieDetails(
  movieId: number,
  mediaType: MediaType = "movie",
): Promise<DeckMovie | null> {
  const key = `${mediaType}:${movieId}`;
  const cached = movieDetailsCache.get(key);
  if (cached && cached.expiresAt > Date.now() && hasUsefulDetails(cached.movie)) {
    return cached.movie;
  }
  const pending = movieDetailsInFlight.get(key);
  if (pending) return pending;
  const request = (async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/movie?movie_id=${movieId}&user_id=${getUserId()}&media_type=${mediaType}`,
        {
          headers: getAuthHeaders(),
        },
      );
      const data = (await res.json()) as {
        ok?: boolean;
        movie?: ApiMovie;
        user_status?: string;
        user_rating?: number;
        tv_progress?: TvProgress;
      };
      if (!data.ok || !data.movie) return null;
      const m = data.movie;
      const result = {
        ...mapApiMovieToDeck(m),
        movie_id: typeof m.movie_id === "number" ? m.movie_id : movieId,
        media_type: m.media_type === "tv" ? "tv" : mediaType,
        user_rating: data.user_rating || 0,
        user_status:
          (data.user_status ?? m.user_status) && (data.user_status ?? m.user_status) !== "none"
            ? (data.user_status ?? m.user_status)
            : undefined,
        tv_progress: data.tv_progress,
      };
      movieDetailsCache.set(key, { movie: result, expiresAt: Date.now() + DETAIL_CACHE_TTL_MS });
      return result;
    } catch (e) {
      return cached?.movie ?? null;
    }
  })();
  movieDetailsInFlight.set(key, request);
  try {
    return await request;
  } finally {
    movieDetailsInFlight.delete(key);
  }
}

export type FetchMoviesResult = {
  movies: DeckMovie[];
  next_cursor: number | null;
};

export type RecommendationParams = {
  target_type?: string;
  min_year?: number;
  max_year?: number;
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
  if (params?.max_year != null) searchParams.set("max_year", String(params.max_year));
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
  const movies: DeckMovie[] = data.movies.map(mapApiMovieToDeck);
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
    next_cursor: typeof data.next_cursor === "number" ? data.next_cursor : null,
  };
}

export async function postSwipe(movie: DeckMovie, action: SwipeAction): Promise<boolean> {
  const payload = {
    user_id: getUserId(),
    movie_id: movie.movie_id,
    action,
    media_type: movie.media_type,
    genre_ids: movie.genre_ids,
    action_id:
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  };
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(`${API_BASE}/api/swipe`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
        keepalive: true,
      });
      if (response.ok) {
        patchLibraryCache({ ...movie, user_status: action }, true);
        window.dispatchEvent(new Event("mmt:taste-updated"));
        return true;
      }
    } catch (e) {
      if (attempt === 1) console.warn("[api.swipe] failed", e);
    }
    if (attempt === 0) await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

export async function rateMovie(
  movieId: number,
  mediaType: MediaType,
  rating: number,
): Promise<void> {
  await fetch(`${API_BASE}/api/rate`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      user_id: getUserId(),
      movie_id: movieId,
      media_type: mediaType,
      rating,
    }),
  })
    .then((response) => {
      if (response.ok) {
        patchLibraryRating(movieId, mediaType, rating);
        window.dispatchEvent(new Event("mmt:taste-updated"));
      }
    })
    .catch((e) => console.warn("[api.rate] failed", e));
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
