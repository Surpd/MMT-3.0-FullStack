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
import {
  fetchLibrary,
  fetchStats,
  fetchTasteSummary,
  type DeckMovie,
  type TasteSummary,
  type UserStats,
} from "@/lib/api";
import { DetailsSheet } from "@/components/tabs/LibraryTab";
import { TV_PROGRESS_EVENT, type TvProgressEventDetail } from "@/components/TvProgressPanel";
import {
  useDeck,
  loadDiscoverSettings,
  saveDiscoverSettings,
  type DiscoverSettings,
} from "@/lib/DeckContext";

type ProfileScreen = "home" | "taste" | "achievements" | "settings";

export function ProfileTab() {
  const user = getTelegramUser();
  const { applyFilters } = useDeck();
  const [screen, setScreen] = useState<ProfileScreen>("home");
  const [loading, setLoading] = useState(true);
  const [liked, setLiked] = useState<DeckMovie[]>([]);
  const [wanted, setWanted] = useState<DeckMovie[]>([]);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [taste, setTaste] = useState<TasteSummary | null>(null);
  const [openSeries, setOpenSeries] = useState<DeckMovie | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchLibrary("liked", 1),
      fetchLibrary("watchlist", 1),
      fetchStats(),
      fetchTasteSummary(),
    ])
      .then(([mine, plans, stats, summary]) => {
        if (!cancelled) {
          setLiked(mine);
          setWanted(plans);
          setUserStats(stats);
          setTaste(summary);
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

  useEffect(() => {
    const handleProgress = (event: Event) => {
      const { tvId, progress } = (event as CustomEvent<TvProgressEventDetail>).detail;
      setLiked((current) =>
        current.map((item) => (item.movie_id === tvId ? { ...item, tv_progress: progress } : item)),
      );
      setOpenSeries((current) =>
        current?.movie_id === tvId ? { ...current, tv_progress: progress } : current,
      );
    };
    window.addEventListener(TV_PROGRESS_EVENT, handleProgress);
    return () => window.removeEventListener(TV_PROGRESS_EVENT, handleProgress);
  }, []);

  if (screen !== "home")
    return (
      <ProfileDetail
        screen={screen}
        liked={liked}
        stats={userStats}
        taste={taste}
        onBack={() => setScreen("home")}
        applyFilters={applyFilters}
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
  const genres = taste?.genres.slice(0, 3) ?? [];
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
          <button
            aria-label="Настройки"
            onClick={() => setScreen("settings")}
            className="flex size-10 items-center justify-center rounded-xl border border-white/10 bg-zinc-900/70 text-zinc-300"
          >
            ⚙
          </button>
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
                      {Math.round(g.share)}% вкуса
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
        <DetailsSheet
          movie={openSeries}
          tab="liked"
          onClose={() => setOpenSeries(null)}
          onUpdate={(updated) => {
            setLiked((items) =>
              items.map((item) => (item.movie_id === updated.movie_id ? updated : item)),
            );
            setOpenSeries(updated);
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
  taste,
  onBack,
  applyFilters,
}: {
  screen: ProfileScreen;
  liked: DeckMovie[];
  stats: UserStats | null;
  taste: TasteSummary | null;
  onBack: () => void;
  applyFilters: (settings: DiscoverSettings) => void;
}) {
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
            {screen === "taste" ? "МОЙ ВКУС" : screen === "settings" ? "НАСТРОЙКИ" : "ДОСТИЖЕНИЯ"}
          </h1>
        </div>
      </div>
      {screen === "taste" ? (
        <TasteView summary={taste} />
      ) : screen === "settings" ? (
        <DiscoverSettingsPanel onClose={onBack} applyFilters={applyFilters} />
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

function DiscoverSettingsPanel({
  onClose,
  applyFilters,
}: {
  onClose: () => void;
  applyFilters: (settings: DiscoverSettings) => void;
}) {
  const [settings, setSettings] = useState<DiscoverSettings>(loadDiscoverSettings);
  const save = () => {
    saveDiscoverSettings(settings);
    applyFilters(settings);
    onClose();
  };
  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 text-[10px] font-bold tracking-[.2em] text-zinc-500">
          ФОРМАТ DISCOVER
        </div>
        <div className="grid grid-cols-3 gap-2">
          {(
            [
              ["mix", "Микс"],
              ["movie", "Фильмы"],
              ["tv", "Сериалы"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setSettings({ ...settings, targetType: value })}
              className={`min-h-11 rounded-xl border text-xs font-semibold ${settings.targetType === value ? "border-neon-cyan/50 bg-neon-cyan/10 text-neon-cyan" : "border-white/10 bg-zinc-900/60 text-zinc-400"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <label className="block text-xs text-zinc-400">
        Минимальный год
        <input
          type="range"
          min="1900"
          max="2026"
          value={settings.minYear}
          onChange={(e) =>
            setSettings({
              ...settings,
              minYear: Math.min(Number(e.target.value), settings.maxYear),
            })
          }
          className="mt-2 w-full accent-cyan-400"
        />
        <input
          type="range"
          min="1950"
          max="2026"
          value={settings.maxYear}
          onChange={(e) =>
            setSettings({
              ...settings,
              maxYear: Math.max(Number(e.target.value), settings.minYear),
            })
          }
          className="mt-2 w-full accent-cyan-400"
        />
        <span className="float-right text-neon-cyan">
          {settings.minYear} — {settings.maxYear}
        </span>
      </label>
      <label className="block text-xs text-zinc-400">
        Минимальный рейтинг
        <input
          type="range"
          min="0"
          max="10"
          step="0.5"
          value={settings.minRating}
          onChange={(e) => setSettings({ ...settings, minRating: Number(e.target.value) })}
          className="mt-2 w-full accent-cyan-400"
        />
        <span className="float-right text-neon-cyan">{settings.minRating.toFixed(1)}</span>
      </label>
      <button
        onClick={save}
        className="h-12 w-full rounded-2xl bg-neon-cyan font-bold text-asphalt"
      >
        Сохранить настройки
      </button>
    </div>
  );
}

function TasteView({ summary }: { summary: TasteSummary | null }) {
  const genres = summary?.genres ?? [];
  const directors = summary?.directors ?? [];
  const actors = summary?.actors ?? [];
  const eras = summary?.eras ?? [];
  const movies = summary?.movie_vs_series.movies ?? 0;
  const series = summary?.movie_vs_series.series ?? 0;
  const total = movies + series;
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-neon-cyan/15 bg-neon-cyan/5 p-4">
        <div className="text-[10px] font-bold tracking-[.2em] text-zinc-500">ПОРТРЕТ ЗРИТЕЛЯ</div>
        <div className="mt-2 text-xl font-bold text-white">
          {genres
            .slice(0, 3)
            .map((genre) => genre.name)
            .join(" · ") || "Пока недостаточно данных"}
        </div>
      </section>
      <section className="rounded-2xl border border-white/8 bg-zinc-900/60 p-4">
        <div className="mb-3 text-[10px] font-bold tracking-[.2em] text-zinc-500">
          ФИЛЬМЫ <span className="text-zinc-700">VS</span> СЕРИАЛЫ
        </div>
        <div className="flex items-end justify-between text-xs font-bold">
          <span className="text-rose-300">
            ФИЛЬМЫ {total ? Math.round((movies / total) * 100) : 0}%
          </span>
          <span className="text-sky-300">
            {total ? Math.round((series / total) * 100) : 0}% СЕРИАЛЫ
          </span>
        </div>
        <div className="mt-2 flex h-3 overflow-hidden rounded-full bg-sky-400/20">
          <div
            className="bg-rose-400"
            style={{ width: `${total ? (movies / total) * 100 : 50}%` }}
          />
        </div>
      </section>
      <section>
        <TasteHeading label="ЖАНРЫ" />
        {genres.length ? (
          <div className="grid grid-cols-2 gap-2">
            {genres.slice(0, 6).map((genre) => (
              <div key={genre.name} className="rounded-xl border border-white/8 bg-zinc-900/60 p-3">
                <div className="truncate text-xs font-bold text-zinc-200">{genre.name}</div>
                <div className="mt-1 text-[10px] text-neon-cyan">{Math.round(genre.share)}%</div>
              </div>
            ))}
            {genres.slice(6).reduce((sum, genre) => sum + genre.share, 0) > 0 && (
              <div className="rounded-xl border border-white/8 bg-zinc-900/40 p-3">
                <div className="text-xs font-bold text-zinc-400">Остальные</div>
                <div className="mt-1 text-[10px] text-zinc-500">
                  {Math.round(genres.slice(6).reduce((sum, genre) => sum + genre.share, 0))}% вкуса
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyLine text="Пока недостаточно данных" />
        )}
      </section>
      {directors.length > 0 && (
        <section>
          <TasteHeading label="РЕЖИССЁРЫ" />{" "}
          <div className="space-y-2">
            {directors.map((person) => (
              <PersonRow key={person.name} person={person} rating={person.rating} />
            ))}
          </div>
        </section>
      )}
      {actors.length > 0 && (
        <section>
          <TasteHeading label="АКТЁРЫ" />{" "}
          <div className="grid grid-cols-2 gap-2">
            {actors.map((person) => (
              <PersonRow key={person.name} person={person} />
            ))}
          </div>
        </section>
      )}
      {eras.length > 0 && (
        <section className="rounded-2xl border border-white/8 bg-zinc-900/60 p-4">
          <TasteHeading label="ТВОЯ ЭПОХА" />
          <div className="mb-3 text-lg font-bold text-white">{eras[0].name}</div>
          <div className="space-y-2">
            {eras.slice(0, 5).map((era) => (
              <div key={era.name} className="flex items-center gap-2 text-[10px] text-zinc-400">
                <span className="w-14">{era.name}</span>
                <span className="h-1.5 flex-1 rounded-full bg-white/10">
                  <span
                    className="block h-full rounded-full bg-neon-cyan"
                    style={{ width: `${era.share}%` }}
                  />
                </span>
                <span className="w-8 text-right">{Math.round(era.share)}%</span>
              </div>
            ))}
          </div>
        </section>
      )}
      {summary?.countries.length ? (
        <section className="rounded-2xl border border-white/8 bg-zinc-900/60 p-4">
          <TasteHeading label="ОТКУДА ТВОЁ КИНО" />
          <div className="space-y-2">
            {summary.countries.map((country) => (
              <div
                key={country.name}
                className="flex items-center justify-between text-xs text-zinc-300"
              >
                <span>{country.name}</span>
                <span className="text-neon-cyan">{Math.round(country.share)}%</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function TasteHeading({ label }: { label: string }) {
  return <div className="mb-2 text-[10px] font-bold tracking-[.2em] text-zinc-500">{label}</div>;
}
function PersonRow({
  person,
  rating,
}: {
  person: { name: string; count: number };
  rating?: number;
}) {
  return (
    <div className="rounded-xl border border-white/8 bg-zinc-900/60 p-3">
      <div className="truncate text-xs font-bold text-zinc-200">{person.name}</div>
      <div className="mt-1 text-[10px] text-zinc-500">
        {person.count} {person.count === 1 ? "тайтл" : "тайтла в коллекции"}
        {rating ? ` · ★ ${rating.toFixed(1)}` : ""}
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
