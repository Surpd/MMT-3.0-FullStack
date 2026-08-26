import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ChevronRight,
  Flame,
  Trophy,
  Bookmark,
  Eye,
  Star,
  Sparkles,
} from "lucide-react";
import { getTelegramUser } from "@/lib/telegram";
import { fetchLibrary, fetchStats, type DeckMovie, type UserStats } from "@/lib/api";
import { TvProgressPanel } from "@/components/TvProgressPanel";

type ProfileScreen = "home" | "taste" | "achievements";

export function ProfileTab() {
  const user = getTelegramUser();
  const [screen, setScreen] = useState<ProfileScreen>("home");
  const [loading, setLoading] = useState(true);
  const [liked, setLiked] = useState<DeckMovie[]>([]);
  const [wanted, setWanted] = useState<DeckMovie[]>([]);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [openSeries, setOpenSeries] = useState<DeckMovie | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchLibrary("liked", 1), fetchLibrary("watchlist", 1), fetchStats()])
      .then(([mine, plans, stats]) => {
        if (!cancelled) {
          setLiked(mine);
          setWanted(plans);
          setUserStats(stats);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (screen !== "home")
    return (
      <ProfileDetail
        screen={screen}
        liked={liked}
        stats={userStats}
        onBack={() => setScreen("home")}
      />
    );

  const displayName = user?.first_name || user?.username || "Киноман";
  const current = liked.find(
    (m) =>
      m.media_type === "tv" &&
      m.tv_progress &&
      m.tv_progress.available_episodes > 0 &&
      m.tv_progress.watched_episodes > 0 &&
      m.tv_progress.watched_episodes < m.tv_progress.available_episodes,
  );
  const seriesCount = liked.filter((m) => m.media_type === "tv").length;
  const genres = getGenres(liked).slice(0, 3);
  const achievements = getAchievements(userStats, liked);

  return (
    <>
      <div className="flex h-full flex-col overflow-y-auto px-5 pb-6 pt-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold tracking-[.25em] text-neon-cyan">
              MY MOVIE TRACKER
            </div>
            <h1 className="font-cinematic text-3xl tracking-wide text-white">ПРОФИЛЬ</h1>
          </div>
        </div>
        <div className="mb-4 flex items-center gap-3 rounded-2xl border border-white/8 bg-zinc-900/55 p-3">
          <div className="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-neon-cyan to-neon-red p-[2px]">
            <div className="flex size-full items-center justify-center overflow-hidden rounded-full bg-zinc-950">
              {user?.photo_url ? (
                <img src={user.photo_url} alt="" className="size-full object-cover" />
              ) : (
                <span className="font-cinematic text-2xl text-white">
                  {displayName[0]?.toUpperCase()}
                </span>
              )}
            </div>
          </div>
          <div className="min-w-0">
            <div className="truncate text-base font-bold text-white">{displayName}</div>
            <div className="truncate text-xs text-zinc-500">
              {user?.username ? `@${user.username}` : "Telegram user"}
            </div>
            <div className="mt-1 text-[10px] font-bold uppercase tracking-wider text-neon-cyan">
              LVL {userStats?.level ?? 1} · {userStats?.title ?? "Киноман"}
            </div>
          </div>
        </div>
        <div className="mb-5 grid grid-cols-3 divide-x divide-white/10 rounded-2xl border border-white/8 bg-zinc-900/55 py-3">
          <MiniStat
            label="МОЁ"
            value={loading ? "—" : liked.length}
            icon={<Eye className="size-3" />}
          />
          <MiniStat
            label="В ПЛАНАХ"
            value={loading ? "—" : wanted.length}
            icon={<Bookmark className="size-3" />}
          />
          <MiniStat
            label="СЕРИАЛЫ"
            value={loading ? "—" : seriesCount}
            icon={<Sparkles className="size-3" />}
          />
        </div>
        <div className="space-y-4">
          <section>
            <SectionLink label="СЕЙЧАС СМОТРЮ" />
            {current ? (
              <CompactCurrent movie={current} onOpen={() => setOpenSeries(current)} />
            ) : (
              <EmptyLine text="Начните сериал, чтобы увидеть прогресс здесь" />
            )}
          </section>
          <section>
            <SectionLink label="МОЙ ВКУС" action="Все" onClick={() => setScreen("taste")} />
            {genres.length ? (
              <div className="flex gap-2">
                {genres.map((g) => (
                  <div
                    key={g.name}
                    className="flex-1 rounded-xl border border-neon-cyan/15 bg-neon-cyan/5 px-2 py-3"
                  >
                    <div className="truncate text-xs font-bold text-zinc-200">{g.name}</div>
                    <div className="mt-1 text-[10px] text-neon-cyan">
                      {Math.round((g.value / Math.max(1, liked.length)) * 100)}% коллекции
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyLine text="Добавьте фильмы, чтобы собрать профиль вкуса" />
            )}
          </section>
          <section>
            <SectionLink
              label="ДОСТИЖЕНИЯ"
              action="Все"
              onClick={() => setScreen("achievements")}
            />
            <div className="flex gap-2">
              {achievements.slice(0, 3).map((a) => (
                <div
                  key={a.label}
                  className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-white/8 bg-zinc-900/60 p-2.5"
                >
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-amber-400/10 text-amber-300">
                    {a.icon}
                  </span>
                  <span className="truncate text-[10px] font-semibold text-zinc-300">
                    {a.label}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
      {openSeries && (
        <ProfileSeriesSheet
          movie={openSeries}
          onClose={() => setOpenSeries(null)}
          onChange={(progress) => {
            setLiked((items) =>
              items.map((item) =>
                item.movie_id === openSeries.movie_id ? { ...item, tv_progress: progress } : item,
              ),
            );
            setOpenSeries((item) => (item ? { ...item, tv_progress: progress } : item));
          }}
        />
      )}
    </>
  );
}

function ProfileDetail({
  screen,
  liked,
  stats,
  onBack,
}: {
  screen: ProfileScreen;
  liked: DeckMovie[];
  stats: UserStats | null;
  onBack: () => void;
}) {
  const genres = getGenres(liked);
  const achievements = getAchievements(stats, liked);
  return (
    <div className="flex h-full flex-col overflow-y-auto px-5 pb-6 pt-5">
      <div className="mb-5 flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex size-10 items-center justify-center rounded-xl border border-white/10 bg-zinc-900/70"
        >
          <ArrowLeft className="size-4" />
        </button>
        <div>
          <div className="text-[10px] font-bold tracking-[.25em] text-neon-cyan">ПРОФИЛЬ</div>
          <h1 className="font-cinematic text-3xl text-white">
            {screen === "taste" ? "МОЙ ВКУС" : "ДОСТИЖЕНИЯ"}
          </h1>
        </div>
      </div>
      {screen === "taste" ? (
        <div className="space-y-2">
          {genres.length ? (
            genres.map((g, i) => (
              <div key={g.name} className="rounded-2xl border border-white/8 bg-zinc-900/60 p-4">
                <div className="flex justify-between text-sm font-bold text-zinc-100">
                  <span>{g.name}</span>
                  <span className="text-neon-cyan">
                    {Math.round((g.value / Math.max(1, liked.length)) * 100)}%
                  </span>
                </div>
                <div className="mt-3 h-2 rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-neon-cyan"
                    style={{
                      width: `${Math.round((g.value / Math.max(1, liked.length)) * 100)}%`,
                      opacity: 1 - i * 0.12,
                    }}
                  />
                </div>
              </div>
            ))
          ) : (
            <EmptyLine text="Пока недостаточно данных" />
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {achievements.map((a) => (
            <div
              key={a.label}
              className="flex items-center gap-3 rounded-2xl border border-white/8 bg-zinc-900/60 p-4"
            >
              <span className="flex size-9 items-center justify-center rounded-xl bg-amber-400/10 text-amber-300">
                {a.icon}
              </span>
              <div>
                <div className="text-sm font-bold text-zinc-100">{a.label}</div>
                <div className="text-xs text-zinc-500">{a.description}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MiniStat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <div className="text-center">
      <div className="mb-1 flex items-center justify-center gap-1 text-[9px] font-bold tracking-wider text-zinc-500">
        {icon}
        {label}
      </div>
      <div className="font-cinematic text-2xl text-white">{value}</div>
    </div>
  );
}
function SectionLink({
  label,
  action,
  onClick,
}: {
  label: string;
  action?: string;
  onClick?: () => void;
}) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <div className="text-[10px] font-bold tracking-[.22em] text-zinc-500">{label}</div>
      {action && (
        <button
          onClick={onClick}
          className="flex items-center gap-1 text-[11px] font-bold text-neon-cyan"
        >
          {action}
          <ChevronRight className="size-3" />
        </button>
      )}
    </div>
  );
}
function CompactCurrent({ movie, onOpen }: { movie: DeckMovie; onOpen: () => void }) {
  const p = movie.tv_progress;
  const total = p?.available_episodes || movie.number_of_episodes || 0;
  const watched = p?.watched_episodes || 0;
  const next = p?.next_episode;
  return (
    <button
      onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-2xl border border-neon-cyan/15 bg-zinc-900/65 p-2.5 text-left"
    >
      <img src={movie.poster} alt="" className="size-14 rounded-xl object-cover" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-bold text-zinc-100">{movie.title}</div>
        <div className="mt-1 text-[11px] text-zinc-400">
          {next
            ? `S${String(next.season_number ?? 1).padStart(2, "0")}E${String(next.episode_number).padStart(2, "0")}`
            : `${watched}/${total} серий`}
        </div>
        <div className="mt-2 h-1.5 rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-neon-cyan"
            style={{ width: total ? `${Math.min(100, (watched / total) * 100)}%` : "0%" }}
          />
        </div>
      </div>
      <ChevronRight className="size-4 text-zinc-600" />
    </button>
  );
}

function ProfileSeriesSheet({
  movie,
  onClose,
  onChange,
}: {
  movie: DeckMovie;
  onClose: () => void;
  onChange: (progress: NonNullable<DeckMovie["tv_progress"]>) => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88dvh] w-full max-w-[440px] overflow-y-auto rounded-t-3xl border border-white/10 bg-zinc-950 p-5"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="min-w-0">
            <div className="truncate text-lg font-bold text-white">{movie.title}</div>
            <div className="text-xs text-zinc-500">Прогресс сериала</div>
          </div>
          <button
            onClick={onClose}
            className="size-9 rounded-full border border-white/10 text-zinc-300"
          >
            ×
          </button>
        </div>
        <TvProgressPanel tvId={movie.movie_id} progress={movie.tv_progress} onChange={onChange} />
      </div>
    </div>
  );
}
function EmptyLine({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-white/10 px-3 py-4 text-center text-xs text-zinc-500">
      {text}
    </div>
  );
}
function getGenres(items: DeckMovie[]) {
  const counts: Record<string, number> = {};
  items.forEach((m) =>
    m.genre_names?.forEach((g) => {
      if (g) counts[g] = (counts[g] ?? 0) + 1;
    }),
  );
  return Object.entries(counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}
function getAchievements(stats: UserStats | null, liked: DeckMovie[]) {
  return [
    {
      label: "Киноман",
      description: `${liked.length} тайтлов в коллекции`,
      icon: <Trophy className="size-4" />,
    },
    {
      label: `${stats?.best_streak ?? 0} дней`,
      description: "Лучший streak квиза",
      icon: <Flame className="size-4" />,
    },
    {
      label: `${liked.filter((m) => m.user_rating).length} оценок`,
      description: "Личные оценки",
      icon: <Star className="size-4" />,
    },
  ];
}
