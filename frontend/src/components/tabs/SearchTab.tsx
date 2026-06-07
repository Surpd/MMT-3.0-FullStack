import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Search, Star, X, Clock, Clapperboard, Users } from "lucide-react";
import { type Movie } from "@/lib/movies";
import { fetchMovieDetails, fetchSearchTags, getUserId, postSwipe, rateMovie, searchMovies, type DeckMovie, type SwipeAction } from "@/lib/api";
import { tgClose, tgHaptic } from "@/lib/telegram";

export function SearchTab({ onOpen }: { onOpen?: (m: Movie) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DeckMovie[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [open, setOpen] = useState<DeckMovie | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length <= 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      searchMovies(trimmed, getUserId())
        .then((movies) => {
          if (!cancelled) setResults(movies);
        })
        .catch((error) => {
          console.warn("[search] failed", error);
          if (!cancelled) setResults([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const handleMovieClick = async (movie: DeckMovie) => {
    setLoadingId(movie.movie_id);
    try {
      const fullMovie = await fetchMovieDetails(movie.movie_id, movie.media_type);
      if (fullMovie) setOpen(fullMovie);
      else setOpen(movie);
    } finally {
      setLoadingId(null);
    }
  };

  const [chips, setChips] = useState<string[]>(["Комедия 2026", "Фантастика", "Триллер 2025", "Топ рейтинг"]);

  useEffect(() => {
    fetchSearchTags().then((tags) => {
      if (tags && tags.length > 0) setChips(tags);
    });
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 space-y-3 px-5 pb-3 pt-4">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title..."
            className="h-12 w-full rounded-2xl border border-white/10 bg-zinc-900/80 pl-11 pr-4 text-sm text-zinc-100 placeholder:text-zinc-500 transition focus:border-neon-cyan/50 focus:outline-none focus:ring-2 focus:ring-neon-cyan/20"
          />
        </div>

        <div className="scrollbar-hide -mx-5 flex gap-2 overflow-x-auto px-5">
          {chips.map((chip) => (
            <span
              key={chip}
              onClick={() => setQuery(chip)}
              className="shrink-0 rounded-full border border-white/10 bg-zinc-900/60 px-3.5 h-8 text-[11px] font-semibold uppercase tracking-wider text-zinc-300 flex items-center cursor-pointer hover:bg-zinc-800 active:scale-95 transition-all"
            >
              {chip}
            </span>
          ))}
        </div>
      </div>

      <div className="mobile-scroll flex-1 px-5 pb-4">
        {loading ? (
          <div className="flex items-center justify-center pt-16">
            <Loader2 className="h-7 w-7 animate-spin text-neon-cyan" />
          </div>
        ) : results.length === 0 ? (
          <div className="pt-16 text-center text-sm text-zinc-500">
            {query.trim().length > 2
              ? "No movies found."
              : "Type at least 3 characters to search."}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <AnimatePresence mode="popLayout">
              {results.map((movie, index) => (
                <PosterTile
                  key={movie.movie_id}
                  movie={movie}
                  index={index}
                  loading={loadingId === movie.movie_id}
                  onOpen={() => {
                    tgHaptic("light");
                    void handleMovieClick(movie);
                  }}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      <AnimatePresence>
        {open && (
          <DetailsSheet
            movie={open}
            onClose={() => setOpen(null)}
            onUpdate={(updated) => {
              setResults((prev) => prev.map((m) => (m.movie_id === updated.movie_id ? updated : m)));
              setOpen(updated);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function PosterTile({
  movie,
  onOpen,
  loading,
  index,
}: {
  movie: DeckMovie;
  onOpen: () => void;
  loading: boolean;
  index: number;
}) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 300, damping: 28, delay: Math.min(index * 0.025, 0.3) }}
      onClick={onOpen}
      className="relative aspect-[2/3] w-full cursor-pointer overflow-hidden rounded-2xl bg-zinc-900 shadow-lg border border-white/5 transition active:scale-95"
    >
      <img src={movie.poster} alt={movie.title} className="h-full w-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent" />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/95 via-black/60 to-transparent p-3 pt-10">
        <div className="truncate text-[12px] font-bold text-white leading-tight">{movie.title}</div>
        {movie.year && <div className="text-[10px] text-zinc-400 mt-0.5">{movie.year}</div>}
      </div>
      {/* TMDB Рейтинг (Слева) */}
      {typeof movie.rating === "number" && movie.rating > 0 && (
        <div className="absolute top-2 left-2 z-10 flex items-center gap-1 rounded-md border border-white/10 bg-black/70 px-1.5 py-0.5 backdrop-blur-md">
          <Star className="h-3 w-3 fill-zinc-400 text-zinc-400" />
          <span className="text-[11px] font-bold text-zinc-300">{movie.rating.toFixed(1)}</span>
        </div>
      )}

      {/* Личная оценка юзера (Справа) */}
      {typeof movie.user_rating === "number" && movie.user_rating > 0 && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-1 rounded-md border border-yellow-500/30 bg-black/70 px-1.5 py-0.5 backdrop-blur-md">
          <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
          <span className="text-[11px] font-bold text-yellow-400">{movie.user_rating}</span>
        </div>
      )}
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <Loader2 className="h-6 w-6 animate-spin text-neon-cyan" />
        </div>
      )}
    </motion.button>
  );
}

function StatusBtn({
  label,
  color,
  onClick,
}: {
  label: string;
  color: "green" | "cyan" | "red";
  onClick: () => void;
}) {
  const colorMap = {
    green: "bg-neon-green/10 border-neon-green/30 text-neon-green",
    cyan: "bg-neon-cyan/10 border-neon-cyan/30 text-neon-cyan",
    red: "bg-neon-red/10 border-neon-red/30 text-neon-red",
  } as const;
  return (
    <button
      onClick={onClick}
      className={`flex-1 h-12 rounded-2xl border font-bold text-sm flex items-center justify-center active:scale-[0.98] transition ${colorMap[color]}`}
    >
      {label}
    </button>
  );
}

function DetailsSheet({
  movie,
  onClose,
  onUpdate,
}: {
  movie: DeckMovie;
  onClose: () => void;
  onUpdate?: (m: DeckMovie) => void;
}) {
  const [localStatus, setLocalStatus] = useState<string | undefined>(movie.user_status);
  const [localRating, setLocalRating] = useState(movie.user_rating || 0);

  useEffect(() => {
    setLocalStatus(movie.user_status);
    setLocalRating(movie.user_rating || 0);
  }, [movie]);

  const handleStatus = (action: SwipeAction) => {
    tgHaptic("medium");
    postSwipe(movie, action);
    const newStatus = action === "archive" ? undefined : action;
    setLocalStatus(newStatus);
    onUpdate?.({ ...movie, user_status: newStatus, user_rating: localRating });
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-5"
      initial={{ backgroundColor: "rgba(0,0,0,0)" }}
      animate={{ backgroundColor: "rgba(0,0,0,0.7)" }}
      exit={{ backgroundColor: "rgba(0,0,0,0)" }}
      onClick={onClose}
    >
      <motion.div
        className="relative flex aspect-[2/3] max-h-[85dvh] w-full max-w-[380px] flex-col overflow-hidden rounded-3xl border border-white/10 bg-zinc-950 shadow-2xl"
        initial={{ scale: 0.9, opacity: 0, y: 15 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 15 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative h-40 shrink-0">
          <img src={movie.poster} alt={movie.title} className="h-full w-full object-cover opacity-60" />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent to-zinc-950" />
          <button
            onClick={onClose}
            className="absolute right-4 top-4 z-10 flex size-8 items-center justify-center rounded-full border border-white/15 bg-black/50 text-white backdrop-blur active:scale-90 transition"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="absolute bottom-2 left-5 right-5">
            <h3 className="font-cinematic text-2xl leading-none tracking-wide text-white">
              {movie.title}
            </h3>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-zinc-400">
              {movie.year && <span>{movie.year}</span>}
              {typeof movie.rating === "number" && movie.rating > 0 && (
                <span className="flex items-center gap-1 text-amber-300">
                  <Star className="h-3 w-3 fill-amber-300" strokeWidth={0} />
                  {movie.rating.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="mobile-scroll relative flex-1 space-y-4 px-5 py-4 scrollbar-hide">
          {movie.genre_names && movie.genre_names.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {movie.genre_names.map((genre) => (
                <span
                  key={genre}
                  className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-300"
                >
                  {genre}
                </span>
              ))}
            </div>
          )}

          {movie.directors?.length || movie.actors?.length || movie.runtime_mins ? (
            <div className="space-y-2 text-sm">
              {movie.runtime_mins ? (
                <div className="flex items-center gap-2 text-zinc-300">
                  <Clock className="h-3.5 w-3.5 text-neon-cyan" />
                  <span>{movie.runtime_mins} min</span>
                </div>
              ) : null}
              {movie.directors && movie.directors.length > 0 && (
                <div className="flex items-start gap-2 text-zinc-300">
                  <Clapperboard className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neon-cyan" />
                  <div>
                    <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                      Director
                    </div>
                    <div className="text-zinc-200">{movie.directors.join(", ")}</div>
                  </div>
                </div>
              )}
              {movie.actors && movie.actors.length > 0 && (
                <div className="flex items-start gap-2 text-zinc-300">
                  <Users className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neon-cyan" />
                  <div>
                    <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                      Cast
                    </div>
                    <div className="text-zinc-200">{movie.actors.join(", ")}</div>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {movie.overview && (
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Description
              </div>
              <p className="text-sm leading-relaxed text-zinc-300">{movie.overview}</p>
            </div>
          )}
        </div>

        <div className="px-5 pb-4 flex flex-col items-center gap-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Ваша оценка</div>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                onClick={() => {
                  setLocalRating(star);
                  tgHaptic("light");
                  void rateMovie(movie.movie_id, movie.media_type, star);
                  onUpdate?.({ ...movie, user_rating: star, user_status: localStatus });
                }}
              >
                <Star
                  className={`h-8 w-8 ${
                    star <= localRating
                      ? "fill-yellow-400 text-yellow-400 drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]"
                      : "text-zinc-700"
                  }`}
                  strokeWidth={1}
                />
              </button>
            ))}
          </div>
        </div>

        <div className="relative p-4 border-t border-white/5 flex gap-2">
          {localStatus === "watchlist" && (
            <>
              <StatusBtn label="Смотрел" color="green" onClick={() => handleStatus("liked")} />
              <StatusBtn label="Удалить" color="red" onClick={() => handleStatus("archive")} />
            </>
          )}
          {localStatus === "liked" && (
            <>
              <StatusBtn label="В планы" color="cyan" onClick={() => handleStatus("watchlist")} />
              <StatusBtn label="Удалить" color="red" onClick={() => handleStatus("archive")} />
            </>
          )}
          {(!localStatus || localStatus === "archive") && (
            <>
              <StatusBtn label="Смотрел" color="green" onClick={() => handleStatus("liked")} />
              <StatusBtn label="В планы" color="cyan" onClick={() => handleStatus("watchlist")} />
            </>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
