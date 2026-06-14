import { useEffect, useState } from "react";
import { motion, AnimatePresence, type PanInfo } from "framer-motion";
import {
  Heart,
  X,
  Bookmark,
  Star,
  Film,
  Tv,
  MessageCircle,
  Clock,
  Users,
  Clapperboard,
  SlidersHorizontal,
  Flame,
} from "lucide-react";
import { tgHaptic, tgNotify, tgOpenTelegramLink } from "@/lib/telegram";
import { 
  postSwipe, 
  rateMovie, 
  formatTvSeasons, 
  formatTvStatus, 
  type DeckMovie, 
  type SwipeAction 
} from "@/lib/api";
import {
  useDeck,
  loadDiscoverSettings,
  saveDiscoverSettings,
  type DiscoverSettings,
} from "@/lib/DeckContext";

const TELEGRAM_BOT_USERNAME = "placeholder_bot";
const SWIPE_THRESHOLD = 110;
const SWIPE_UP_THRESHOLD = 110;

function TvBadges({ movie }: { movie: DeckMovie }) {
  if (movie.media_type !== "tv") return null;

  const status = formatTvStatus(movie.tv_status);
  const isFinished = status === "Завершен";

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      <span className="px-2 py-0.5 text-[10px] font-semibold tracking-wide rounded-full bg-neon-cyan/10 backdrop-blur-md border border-neon-cyan/25 text-neon-cyan">
        {formatTvSeasons(movie.seasons)}
      </span>
      <span
        className={`px-2 py-0.5 text-[10px] font-semibold tracking-wide rounded-full backdrop-blur-md border ${
          isFinished
            ? "bg-white/5 border-white/10 text-zinc-400"
            : "bg-neon-green/10 border-neon-green/25 text-neon-green"
        }`}
      >
        {status}
      </span>
    </div>
  );
}

export function DiscoverTab() {
  const { deck, setDeck, hasMore, loading, loadMore, applyFilters } = useDeck();
  const [exitDir, setExitDir] = useState<SwipeAction | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [draftSettings, setDraftSettings] = useState<DiscoverSettings>(loadDiscoverSettings);

  useEffect(() => {
    if (!loading && hasMore && deck.length > 0 && deck.length <= 3) {
      loadMore();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deck.length, hasMore, loading]);

  const top = deck[0];
  const next = deck[1];
  const after = deck[2];

  const decide = (movie: DeckMovie, action: SwipeAction) => {
    setExitDir(action);
    tgHaptic("medium");
    tgNotify(action === "archive" ? "warning" : "success");
    postSwipe(movie, action);
    setTimeout(() => {
      setDeck((d) => d.slice(1));
      setExitDir(null);
    }, 220);
  };

  const handleApplySettings = () => {
    tgHaptic("medium");
    saveDiscoverSettings(draftSettings);
    setSettingsOpen(false);
    applyFilters(draftSettings);
  };

  return (
    <div className="relative h-full flex flex-col swipe-area">
      <div className="shrink-0 flex items-center justify-between px-5 pt-4 pb-2 relative z-[200]">
        <div className="flex items-center gap-2">
          <Flame className="w-5 h-5 text-neon-cyan" strokeWidth={2.4} />
          <h1 className="font-cinematic text-xl text-white tracking-wide">Discover</h1>
        </div>
        <div className="relative">
          <button
            onClick={() => {
              tgHaptic("light");
              if (!settingsOpen) setDraftSettings(loadDiscoverSettings());
              setSettingsOpen((v) => !v);
            }}
            className={`size-10 rounded-full border flex items-center justify-center active:scale-90 transition ${
              settingsOpen
                ? "bg-neon-cyan/20 border-neon-cyan/50 text-neon-cyan shadow-[0_0_24px_rgba(34,211,238,0.35)]"
                : "bg-zinc-900/80 border-white/10 text-neon-cyan hover:bg-neon-cyan/10 shadow-[0_0_20px_rgba(34,211,238,0.15)]"
            }`}
            aria-label="Настройки поиска"
            aria-expanded={settingsOpen}
          >
            <SlidersHorizontal className="w-5 h-5" strokeWidth={2.2} />
          </button>
          <AnimatePresence>
            {settingsOpen && (
              <DiscoverSettingsPopover
                settings={draftSettings}
                onChange={setDraftSettings}
                onClose={() => setSettingsOpen(false)}
                onApply={handleApplySettings}
              />
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className="relative flex-1 px-5 pb-2 flex items-center justify-center">
        {loading ? (
          <EmptyDeck state="loading" />
        ) : deck.length === 0 ? (
          <EmptyDeck state="empty" />
        ) : (
          <div className="relative w-full max-w-[380px] aspect-[2/3] perspective-1000">
            {after && (
              <CardShell
                key={after.movie_id + "-3"}
                style={{ transform: "translateY(24px) scale(0.9)", opacity: 0.35 }}
              >
                <img src={after.poster} alt="" className="w-full h-full object-cover" />
              </CardShell>
            )}
            {next && (
              <CardShell
                key={next.movie_id + "-2"}
                style={{ transform: "translateY(12px) scale(0.95)", opacity: 0.7 }}
              >
                <img src={next.poster} alt="" className="w-full h-full object-cover" />
              </CardShell>
            )}
            {top && (
              <SwipeCard
                key={top.movie_id}
                movie={top}
                exitDir={exitDir}
                onDecide={(d) => decide(top, d)}
              />
            )}
          </div>
        )}
      </div>

      {top && !loading && !settingsOpen && (
        <div className="relative z-[100] pointer-events-auto flex items-center justify-center gap-6 pb-4">
          <ActionButton color="red" label="Archive" onClick={() => decide(top, "archive")}>
            <X className="w-7 h-7" strokeWidth={2.5} />
          </ActionButton>
          <ActionButton color="cyan" label="Watchlist" onClick={() => decide(top, "watchlist")}>
            <Bookmark className="w-6 h-6" strokeWidth={2.5} />
          </ActionButton>
          <ActionButton color="green" label="Liked" onClick={() => decide(top, "liked")}>
            <Heart className="w-7 h-7" strokeWidth={2.5} />
          </ActionButton>
        </div>
      )}
    </div>
  );
}

function CardShell({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className="absolute inset-0 rounded-3xl overflow-hidden bg-zinc-900 border border-white/10"
      style={style}
    >
      {children}
    </div>
  );
}

function SwipeCard({
  movie,
  onDecide,
  exitDir,
}: {
  movie: DeckMovie;
  onDecide: (d: SwipeAction) => void;
  exitDir: SwipeAction | null;
}) {
  const [drag, setDrag] = useState({ x: 0, y: 0 });
  const [flipped, setFlipped] = useState(false);
  const [localRating, setLocalRating] = useState(movie.user_rating || 0);

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    const { offset, velocity } = info;
    if (offset.y < -SWIPE_UP_THRESHOLD || velocity.y < -800) {
      if (Math.abs(offset.y) > Math.abs(offset.x)) {
        onDecide("watchlist");
        return;
      }
    }
    if (offset.x > SWIPE_THRESHOLD || velocity.x > 800) {
      onDecide("liked");
      return;
    }
    if (offset.x < -SWIPE_THRESHOLD || velocity.x < -800) {
      onDecide("archive");
      return;
    }
    setDrag({ x: 0, y: 0 });
  };

  const exitX = exitDir === "liked" ? 600 : exitDir === "archive" ? -600 : 0;
  const exitY = exitDir === "watchlist" ? -800 : 0;
  const likedOp = Math.max(0, Math.min(1, drag.x / 140));
  const dislikeOp = Math.max(0, Math.min(1, -drag.x / 140));
  const watchlistOp = Math.max(0, Math.min(1, -drag.y / 140));
  const rotate = drag.x / 18;

  return (
    <motion.div
      className={`absolute inset-0 preserve-3d ${flipped ? "pointer-events-none" : "pointer-events-auto"}`}
      animate={
        exitDir
          ? { x: exitX, y: exitY, rotate: exitX / 20, opacity: 0 }
          : { x: drag.x, y: drag.y, rotate, rotateY: flipped ? 180 : 0 }
      }
      transition={
        exitDir
          ? { duration: 0.22, ease: "easeOut" }
          : { type: "spring", stiffness: 320, damping: 28 }
      }
      drag={!flipped}
      dragElastic={0.6}
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      onDrag={(_, info) => setDrag({ x: info.offset.x, y: info.offset.y })}
      onDragEnd={(e, info) => {
        handleDragEnd(e, info);
      }}
      style={{ touchAction: flipped ? "pan-y" : "none" }}
    >
      <div
        className="absolute inset-0 rounded-3xl overflow-hidden bg-zinc-900 border border-white/10 card-glow backface-hidden cursor-grab active:cursor-grabbing"
        style={{ pointerEvents: flipped ? "none" : "auto" }}
      >
        <img
          src={movie.poster}
          alt={movie.title}
          className="w-full h-full object-cover pointer-events-none select-none"
          draggable={false}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-asphalt via-asphalt/30 to-transparent pointer-events-none" />

        {!flipped && (
          <div
            className="absolute inset-0 z-10"
            onClick={(e) => {
              e.stopPropagation();
              tgHaptic("light");
              setFlipped(true);
            }}
          />
        )}

        {typeof movie.rating === "number" && movie.rating > 0 && (
          <div
            className={`absolute top-4 left-4 flex items-center gap-1 px-2.5 py-1 rounded-full backdrop-blur-md border text-sm font-bold ${
              movie.rating >= 7
                ? "bg-amber-400/20 border-amber-300/50 text-amber-300"
                : "bg-black/50 border-white/15 text-zinc-200"
            }`}
          >
            <Star
              className={`w-3.5 h-3.5 ${movie.rating >= 7 ? "fill-amber-300" : "fill-zinc-300"}`}
              strokeWidth={0}
            />
            {movie.rating.toFixed(1)}
          </div>
        )}

        {movie.reason && (
          <div className="absolute top-4 right-4 max-w-[60%] px-3 py-1 rounded-full bg-black/50 backdrop-blur-md border border-white/15 text-[10px] uppercase tracking-wider text-zinc-200 font-semibold truncate">
            {movie.reason}
          </div>
        )}

        <div
          className="absolute top-6 left-1/2 -translate-x-1/2 px-4 py-1.5 border-[3px] border-neon-green text-neon-green font-cinematic text-2xl tracking-widest rounded-lg -rotate-12 pointer-events-none"
          style={{ opacity: likedOp }}
        >
          LIKED
        </div>
        <div
          className="absolute top-6 right-6 px-4 py-1.5 border-[3px] border-neon-red text-neon-red font-cinematic text-2xl tracking-widest rounded-lg rotate-12 pointer-events-none"
          style={{ opacity: dislikeOp }}
        >
          NOPE
        </div>
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 px-4 py-1.5 border-[3px] border-neon-cyan text-neon-cyan font-cinematic text-2xl tracking-widest rounded-lg pointer-events-none"
          style={{ opacity: watchlistOp }}
        >
          WATCHLIST
        </div>

        <div className="absolute bottom-0 inset-x-0 p-6 pointer-events-none">
          <h2 className="font-cinematic text-4xl text-white tracking-wide leading-none">
            {movie.title}
          </h2>
          <div className="flex items-center gap-2 mt-2 text-xs text-zinc-300">
            {movie.media_type === "tv" ? (
              <Tv className="w-3.5 h-3.5 text-neon-cyan" />
            ) : (
              <Film className="w-3.5 h-3.5 text-neon-cyan" />
            )}
            {movie.year && <span>{movie.year}</span>}
            <span className="uppercase tracking-wider text-zinc-500">
              {movie.media_type === "tv" ? "TV" : "Movie"}
            </span>
          </div>
          <TvBadges movie={movie} />
          {movie.genre_names && movie.genre_names.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {movie.genre_names.slice(0, 4).map((g) => (
                <span
                  key={g}
                  className="px-2 py-0.5 text-[10px] uppercase tracking-wider rounded-full bg-white/10 backdrop-blur-md border border-white/10 text-zinc-200"
                >
                  {g}
                </span>
              ))}
            </div>
          )}
          <p className="mt-3 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
            Tap card for details
          </p>
        </div>
      </div>

      <div
        className="absolute inset-0 z-[100] pointer-events-auto rounded-3xl overflow-hidden bg-zinc-950 border border-white/10 card-glow backface-hidden rotate-y-180 flex flex-col"
        style={{ pointerEvents: flipped ? "auto" : "none", zIndex: flipped ? 100 : 0 }}
      >
        <div className="relative h-40 shrink-0">
          <img src={movie.poster} alt="" className="w-full h-full object-cover opacity-60" />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent to-zinc-950" />
          <button
            onClick={(e) => {
              e.stopPropagation();
              tgHaptic("light");
              setFlipped(false);
            }}
            className="absolute top-3 right-3 z-[100] pointer-events-auto size-8 rounded-full bg-black/60 backdrop-blur border border-white/15 flex items-center justify-center text-white"
            aria-label="Close details"
          >
            <X className="w-4 h-4" />
          </button>
          <div className="absolute bottom-2 left-4 right-4">
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
        <div className="relative z-[100] pointer-events-auto flex-1 mobile-scroll px-5 py-4 space-y-4 scrollbar-hide">
          {movie.genre_names && movie.genre_names.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {movie.genre_names.map((g) => (
                <span
                  key={g}
                  className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider bg-white/5 border border-white/10 rounded-full text-zinc-300"
                >
                  {g}
                </span>
              ))}
            </div>
          )}
          {(movie.directors?.length || movie.actors?.length || movie.runtime_mins) && (
            <div className="space-y-2 text-sm">
              {movie.runtime_mins ? (
                <div className="flex items-center gap-2 text-zinc-300">
                  <Clock className="w-3.5 h-3.5 text-neon-cyan" />
                  <span>{movie.runtime_mins} min</span>
                </div>
              ) : null}
              {movie.directors && movie.directors.length > 0 && (
                <div className="flex items-start gap-2 text-zinc-300">
                  <Clapperboard className="w-3.5 h-3.5 mt-0.5 text-neon-cyan shrink-0" />
                  <div>
                    <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-500 font-semibold">
                      Director{movie.directors.length > 1 ? "s" : ""}
                    </div>
                    <div className="text-zinc-200">{movie.directors.join(", ")}</div>
                  </div>
                </div>
              )}
              {movie.actors && movie.actors.length > 0 && (
                <div className="flex items-start gap-2 text-zinc-300">
                  <Users className="w-3.5 h-3.5 mt-0.5 text-neon-cyan shrink-0" />
                  <div>
                    <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-500 font-semibold">
                      Cast
                    </div>
                    <div className="text-zinc-200">{movie.actors.join(", ")}</div>
                  </div>
                </div>
              )}
            </div>
          )}
          {movie.overview && (
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-semibold mb-1">
                Overview
              </div>
              <p className="text-zinc-300 text-sm leading-relaxed">{movie.overview}</p>
            </div>
          )}
        </div>
        <div className="px-5 pb-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500 mb-2">
            Ваша оценка
          </div>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                onClick={(e) => {
                  e.stopPropagation();
                  tgHaptic("light");
                  setLocalRating(star);
                  void rateMovie(movie.movie_id, movie.media_type, star);
                }}
                className="active:scale-95 transition"
                aria-label={`Rate ${star} star${star > 1 ? "s" : ""}`}
              >
                <Star
                  className={`w-7 h-7 ${
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
        <div className="relative z-[100] pointer-events-auto p-4 border-t border-white/5">
          <button
            onClick={(e) => {
              e.stopPropagation();
            // tgHaptic("medium");
              tgOpenTelegramLink(
                `https://t.me/${TELEGRAM_BOT_USERNAME}?start=movie_${movie.movie_id}`,
              );
            }}
            className="w-full h-12 rounded-2xl bg-neon-cyan/15 border border-neon-cyan/40 text-neon-cyan font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition shadow-[0_0_30px_rgba(34,211,238,0.25)]"
          >
            <MessageCircle className="w-4 h-4" />
            Подробнее в боте
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function ActionButton({
  children,
  onClick,
  color,
  label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  color: "red" | "green" | "cyan";
  label: string;
}) {
  const colorMap = {
    red: "border-neon-red/40 text-neon-red hover:bg-neon-red/10",
    green:
      "border-neon-green/50 text-neon-green hover:bg-neon-green/10 shadow-[0_0_30px_rgba(74,222,128,0.25)]",
    cyan: "border-neon-cyan/50 text-neon-cyan hover:bg-neon-cyan/10 shadow-[0_0_30px_rgba(34,211,238,0.25)]",
  } as const;
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className={`size-14 rounded-full bg-zinc-900/80 border-2 ${colorMap[color]} flex items-center justify-center transition-all active:scale-90`}
    >
      {children}
    </button>
  );
}

function EmptyDeck({ state }: { state: "loading" | "empty" }) {
  return (
    <div className="text-center px-6">
      <motion.div
        className="font-cinematic text-3xl text-white tracking-wide mb-3"
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      >
        {state === "loading" ? "Подбираем новые фильмы..." : "Нет новых рекомендаций"}
      </motion.div>
      <p className="text-zinc-500 text-xs">
        {state === "loading" ? "Loading fresh picks for you" : "Попробуйте позже или обновите рекомендации"}
      </p>
    </div>
  );
}

function DiscoverSettingsPopover({
  settings,
  onChange,
  onClose,
  onApply,
}: {
  settings: DiscoverSettings;
  onChange: (s: DiscoverSettings) => void;
  onClose: () => void;
  onApply: () => void;
}) {
  const formatOptions: { value: DiscoverSettings["targetType"]; label: string }[] = [
    { value: "mix", label: "Смесь" },
    { value: "movie", label: "Фильмы" },
    { value: "tv", label: "Сериалы" },
  ];

  return (
    <>
      <motion.div
        className="fixed inset-0 z-[190] bg-black/40"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        aria-hidden
      />
      <motion.div
        className="fixed top-[60px] right-5 z-[200] w-[min(320px,calc(100vw-40px))] rounded-2xl border border-white/10 bg-zinc-950/95 backdrop-blur-xl shadow-[0_16px_48px_rgba(0,0,0,0.55),0_0_32px_rgba(34,211,238,0.12)] overflow-hidden"
        initial={{ opacity: 0, scale: 0.92, y: -8, transformOrigin: "top right" }}
        animate={{ opacity: 1, scale: 1, y: 0, transformOrigin: "top right" }}
        exit={{ opacity: 0, scale: 0.92, y: -8, transformOrigin: "top right" }}
        transition={{ type: "spring", stiffness: 420, damping: 30 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
          <div>
            <h2 className="font-cinematic text-lg text-white tracking-wide leading-none">Фильтры</h2>
            <p className="text-[9px] text-zinc-500 mt-1 uppercase tracking-wider">Рекомендации</p>
          </div>
          <button
            onClick={onClose}
            className="size-7 rounded-full bg-black/50 backdrop-blur border border-white/15 flex items-center justify-center text-white active:scale-90 transition"
            aria-label="Закрыть"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="px-4 py-3 space-y-4 max-h-[min(52dvh,380px)] overflow-y-auto scrollbar-hide">
          <div>
            <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-zinc-500 mb-2">
              Формат
            </div>
            <div className="flex gap-1.5">
              {formatOptions.map((opt) => {
                const active = settings.targetType === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => onChange({ ...settings, targetType: opt.value })}
                    className={`flex-1 h-9 rounded-xl border text-xs font-bold transition active:scale-[0.98] ${
                      active
                        ? "bg-neon-cyan/15 border-neon-cyan/50 text-neon-cyan"
                        : "bg-zinc-900/80 border-white/10 text-zinc-400"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Год
              </div>
              <span className="text-xs text-neon-cyan font-semibold">От {settings.minYear}</span>
            </div>
            <input
              type="range"
              min={1950}
              max={2026}
              step={1}
              value={settings.minYear}
              onChange={(e) => onChange({ ...settings, minYear: Number(e.target.value) })}
              className="w-full accent-neon-cyan h-1.5 rounded-full bg-zinc-800 appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-[9px] text-zinc-600 mt-0.5">
              <span>1950</span>
              <span>2026</span>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Рейтинг
              </div>
              <span className="text-xs text-neon-cyan font-semibold">От {settings.minRating.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min={5}
              max={9}
              step={0.5}
              value={settings.minRating}
              onChange={(e) => onChange({ ...settings, minRating: Number(e.target.value) })}
              className="w-full accent-neon-cyan h-1.5 rounded-full bg-zinc-800 appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-[9px] text-zinc-600 mt-0.5">
              <span>5.0</span>
              <span>9.0</span>
            </div>
          </div>
        </div>

        <div className="px-4 pb-4 pt-1">
          <button
            onClick={onApply}
            className="w-full h-10 rounded-xl bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan font-bold text-sm flex items-center justify-center active:scale-[0.98] transition shadow-[0_0_24px_rgba(34,211,238,0.25)]"
          >
            Применить
          </button>
        </div>
      </motion.div>
    </>
  );
}