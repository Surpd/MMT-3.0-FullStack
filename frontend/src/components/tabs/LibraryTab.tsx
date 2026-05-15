import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Star, X, MessageCircle } from "lucide-react";
import { tgHaptic, tgClose } from "@/lib/telegram";
import { fetchLibrary, type DeckMovie, type LibraryStatus } from "@/lib/api";

const TABS: { key: LibraryStatus; label: string }[] = [
  { key: "liked", label: "Смотрел" },
  { key: "watchlist", label: "Хочу" },
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

      <div className="flex-1 overflow-y-auto px-5 pb-4">
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
        {open && <DetailsSheet movie={open} onClose={() => setOpen(null)} />}
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
      className="relative aspect-[2/3] rounded-xl overflow-hidden bg-zinc-900 border border-white/5 active:scale-95 transition"
    >
      <img
        src={movie.poster}
        alt={movie.title}
        className={`w-full h-full object-cover ${isArchive ? "grayscale opacity-60" : ""}`}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent" />
      {typeof movie.rating === "number" && movie.rating > 0 && (
        <div className="absolute bottom-1.5 left-1.5 right-1.5 flex items-center gap-1 text-[10px]">
          <Star className="w-2.5 h-2.5 fill-amber-300 text-amber-300" strokeWidth={0} />
          <span className="text-white font-semibold">{movie.rating.toFixed(1)}</span>
        </div>
      )}
    </motion.button>
  );
}

function DetailsSheet({ movie, onClose }: { movie: DeckMovie; onClose: () => void }) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end justify-center"
      initial={{ backgroundColor: "rgba(0,0,0,0)" }}
      animate={{ backgroundColor: "rgba(0,0,0,0.7)" }}
      exit={{ backgroundColor: "rgba(0,0,0,0)" }}
      onClick={onClose}
    >
      <motion.div
        className="relative w-full max-w-[440px] bg-zinc-950 rounded-t-3xl border-t border-white/10 overflow-hidden max-h-[90dvh] flex flex-col"
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={{ type: "spring", stiffness: 300, damping: 32 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative h-56 shrink-0">
          <img src={movie.poster} alt={movie.title} className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent" />
          <button
            onClick={onClose}
            className="absolute top-4 right-4 size-9 rounded-full bg-black/50 backdrop-blur border border-white/10 flex items-center justify-center text-white"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="absolute -bottom-px inset-x-0 p-5">
            <h2 className="font-cinematic text-3xl text-white tracking-wide leading-none">
              {movie.title}
            </h2>
            <div className="flex items-center gap-2 mt-2 text-xs text-zinc-300">
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
        <div className="overflow-y-auto p-5 space-y-3 scrollbar-hide">
          {movie.genre_names && movie.genre_names.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {movie.genre_names.map((g) => (
                <span
                  key={g}
                  className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wider bg-white/5 border border-white/10 rounded-full text-zinc-300"
                >
                  {g}
                </span>
              ))}
            </div>
          )}
          {movie.overview && (
            <p className="text-zinc-300 text-sm leading-relaxed">{movie.overview}</p>
          )}
          <button
            onClick={() => {
              tgHaptic("medium");
              tgClose();
            }}
            className="w-full h-12 rounded-2xl bg-neon-cyan/15 border border-neon-cyan/40 text-neon-cyan font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition shadow-[0_0_30px_rgba(34,211,238,0.25)]"
          >
            <MessageCircle className="w-4 h-4" />
            Подробнее в боте
          </button>
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
