import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Star, X, Clock, Clapperboard, Users } from "lucide-react";
import { tgHaptic } from "@/lib/telegram";
import { TMDB_IMG, fetchLibrary, postSwipe, rateMovie, type DeckMovie, type LibraryStatus, type SwipeAction } from "@/lib/api";

const TABS: { key: LibraryStatus; label: string }[] = [
  { key: "liked", label: "Ваши лайки" },
  { key: "watchlist", label: "Буду смотреть" },
  { key: "archive", label: "Архив" },
];

export function LibraryTab() {
  const [tab, setTab] = useState<LibraryStatus>("liked");
  const [items, setItems] = useState<DeckMovie[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<DeckMovie | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchLibrary(tab, 1)
      .then((list) => {
        if (!cancelled) setItems(list);
      })
      .catch((e) => {
        console.warn("[library] failed", e);
        if (!cancelled) setItems([]);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [tab]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-4 pb-3 shrink-0">
        <h1 className="font-cinematic text-3xl text-white tracking-wide mb-3">
          Библиотека
        </h1>
        <div className="flex bg-zinc-900/70 border border-white/10 rounded-2xl p-1 relative">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => {
                tgHaptic("light");
                setTab(t.key);
              }}
              className="relative flex-1 h-9 text-[11px] font-bold uppercase tracking-wider z-10 transition-colors"
              style={{ color: tab === t.key ? "var(--asphalt)" : "rgb(228 228 231)" }}
            >
              {tab === t.key && (
                <motion.div
                  layoutId="lib-pill"
                  className="absolute inset-0 bg-neon-cyan rounded-xl shadow-[0_0_20px_rgba(34,211,238,0.4)]"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <span className="relative">{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 mobile-scroll no-scrollbar px-5 pb-4">
        {loading ? (
          <div className="grid grid-cols-3 gap-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className="aspect-[2/3] rounded-xl bg-zinc-900/60 border border-white/5 animate-pulse"
              />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState tab={tab} />
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <AnimatePresence mode="popLayout">
              {items.map((m) => (
                <Tile
                  key={m.movie_id}
                  movie={m}
                  isArchive={tab === "archive"}
                  onOpen={() => setOpen(m)}
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
            tab={tab}
            onClose={() => setOpen(null)}
            onUpdate={(updated) => {
              const shouldRemove = !updated.user_status || updated.user_status !== tab;
              setItems((prev) =>
                shouldRemove
                  ? prev.filter((m) => m.movie_id !== updated.movie_id)
                  : prev.map((m) => (m.movie_id === updated.movie_id ? updated : m)),
              );
              if (shouldRemove) setOpen(null);
              else setOpen(updated);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function Tile({
  movie,
  isArchive,
  onOpen,
}: {
  movie: DeckMovie;
  isArchive: boolean;
  onOpen: () => void;
}) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 300, damping: 28 }}
      onClick={() => {
        tgHaptic("light");
        onOpen();
      }}
      className="relative aspect-[2/3] w-full cursor-pointer overflow-hidden rounded-2xl bg-zinc-900 shadow-lg border border-white/5"
    >
      <img
        src={movie.poster_path ? `${TMDB_IMG}${movie.poster_path}` : movie.poster}
        alt={movie.title}
        className={`h-full w-full object-cover ${isArchive ? "grayscale opacity-60" : ""}`}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent" />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/95 via-black/60 to-transparent p-3 pt-10">
        <div className="truncate text-[12px] font-bold text-white leading-tight">{movie.title}</div>
        {movie.year && <div className="text-[10px] text-zinc-400 mt-0.5">{movie.year}</div>}
      </div>
      {typeof movie.user_rating === "number" && movie.user_rating > 0 ? (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-1 rounded-md border border-white/10 bg-black/70 px-1.5 py-0.5 backdrop-blur-md">
          <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
          <span className="text-[11px] font-bold text-white">{movie.user_rating}</span>
        </div>
      ) : null}
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
  tab,
  onClose,
  onUpdate,
}: {
  movie: DeckMovie;
  tab: LibraryStatus;
  onClose: () => void;
  onUpdate?: (m: DeckMovie) => void;
}) {
  const [localRating, setLocalRating] = useState(movie.user_rating || 0);
  const [localStatus, setLocalStatus] = useState<string | undefined>(movie.user_status);

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
        className="relative w-full max-w-[380px] aspect-[2/3] max-h-[85dvh] bg-zinc-950 rounded-3xl border border-white/10 overflow-hidden flex flex-col shadow-2xl"
        initial={{ scale: 0.9, opacity: 0, y: 15 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 15 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Шапка карточки */}
        <div className="relative h-40 shrink-0">
          <img src={movie.poster} alt={movie.title} className="w-full h-full object-cover opacity-60" />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent to-zinc-950" />
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-10 size-8 rounded-full bg-black/50 backdrop-blur border border-white/15 flex items-center justify-center text-white active:scale-90 transition"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
          <div className="absolute bottom-2 left-5 right-5">
            <h3 className="font-cinematic text-2xl text-white tracking-wide leading-none">
              {movie.title}
            </h3>
            <div className="flex items-center gap-2 mt-1 text-[11px] text-zinc-400">
              {movie.year && <span>{movie.year}</span>}
              {typeof movie.rating === "number" && movie.rating > 0 && (
                <span className="flex items-center gap-1 text-amber-300">
                  <Star className="w-3 h-3 fill-amber-300" strokeWidth={0} />
                  {movie.rating.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Прокручиваемый контент (Жанры, Актеры, Описание) */}
        <div className="relative flex-1 mobile-scroll px-5 py-4 space-y-4 scrollbar-hide">
          {movie.genre_names && movie.genre_names.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {movie.genre_names.map((g) => (
                <span key={g} className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider bg-white/5 border border-white/10 rounded-full text-zinc-300">
                  {g}
                </span>
              ))}
            </div>
          )}

          {(movie.directors?.length || movie.actors?.length || movie.runtime_mins) ? (
            <div className="space-y-2 text-sm">
              {movie.runtime_mins ? (
                <div className="flex items-center gap-2 text-zinc-300">
                  <Clock className="w-3.5 h-3.5 text-neon-cyan" />
                  <span>{movie.runtime_mins} мин</span>
                </div>
              ) : null}
              {movie.directors && movie.directors.length > 0 && (
                <div className="flex items-start gap-2 text-zinc-300">
                  <Clapperboard className="w-3.5 h-3.5 mt-0.5 text-neon-cyan shrink-0" />
                  <div>
                    <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-500 font-semibold">Режиссер</div>
                    <div className="text-zinc-200">{movie.directors.join(", ")}</div>
                  </div>
                </div>
              )}
              {movie.actors && movie.actors.length > 0 && (
                <div className="flex items-start gap-2 text-zinc-300">
                  <Users className="w-3.5 h-3.5 mt-0.5 text-neon-cyan shrink-0" />
                  <div>
                    <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-500 font-semibold">В ролях</div>
                    <div className="text-zinc-200">{movie.actors.join(", ")}</div>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {movie.overview && (
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-semibold mb-1">
                Описание
              </div>
              <p className="text-zinc-300 text-sm leading-relaxed">{movie.overview}</p>
            </div>
          )}
        </div>

        {/* Кнопки действий */}
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
                }}
              >
                <Star
                  className={`w-8 h-8 ${
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
          {tab === "liked" ? (
            <>
              <StatusBtn label="В планы" color="cyan" onClick={() => handleStatus("watchlist")} />
              <StatusBtn label="Удалить" color="red" onClick={() => handleStatus("archive")} />
            </>
          ) : tab === "watchlist" ? (
            <>
              <StatusBtn label="Смотрел" color="green" onClick={() => handleStatus("liked")} />
              <StatusBtn label="Удалить" color="red" onClick={() => handleStatus("archive")} />
            </>
          ) : localStatus === "liked" ? (
            <>
              <StatusBtn label="В планы" color="cyan" onClick={() => handleStatus("watchlist")} />
              <StatusBtn label="Удалить" color="red" onClick={() => handleStatus("archive")} />
            </>
          ) : (
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

function EmptyState({ tab }: { tab: LibraryStatus }) {
  const msg =
    tab === "liked"
      ? "Свайпни вправо, чтобы добавить фильм сюда."
      : tab === "watchlist"
        ? "Свайпни вверх, чтобы сохранить на потом."
        : "Архив пока пуст.";
  return (
    <div className="text-center pt-20 px-6">
      <div className="font-cinematic text-3xl text-white tracking-wide mb-2">
        ПУСТО
      </div>
      <p className="text-zinc-500 text-sm">{msg}</p>
    </div>
  );
}
