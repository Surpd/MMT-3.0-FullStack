import { useEffect, useState } from "react";
import { Check, ChevronDown, ChevronRight } from "lucide-react";
import { API_BASE, getAuthHeaders, getUserId, type TvProgress } from "@/lib/api";

export const TV_PROGRESS_EVENT = "mmt:tv-progress";
export type TvProgressEventDetail = { tvId: number; progress: TvProgress };

function publishProgress(tvId: number, progress: TvProgress) {
  window.dispatchEvent(
    new CustomEvent<TvProgressEventDetail>(TV_PROGRESS_EVENT, { detail: { tvId, progress } }),
  );
}

export function TvProgressPanel({
  tvId,
  progress,
  onChange,
}: {
  tvId: number;
  progress?: TvProgress;
  onChange: (progress: TvProgress) => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [loadingSeason, setLoadingSeason] = useState<number | null>(null);
  const [notifications, setNotifications] = useState(false);
  const [loaded, setLoaded] = useState(progress);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (progress) {
      setLoaded(progress);
      setNotifications(Boolean(progress.notification_enabled));
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/api/tv/progress?tv_id=${tvId}&user_id=${getUserId()}`, {
      headers: getAuthHeaders(),
    })
      .then((response) => response.json())
      .then((data: { progress?: TvProgress }) => {
        if (!cancelled && data.progress) {
          setLoaded(data.progress);
          setNotifications(Boolean(data.progress.notification_enabled));
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [progress, tvId]);
  if (!loaded) return <div className="text-[11px] text-zinc-500">Загружаю сезоны…</div>;

  const update = async (
    url: string,
    body: { season_number: number; episode_number?: number; watched: boolean },
  ) => {
    const previous = loaded;
    const optimistic = applyOptimisticProgress(previous, body);
    setError(null);
    setSaving(true);
    setLoaded(optimistic);
    onChange(optimistic);
    publishProgress(tvId, optimistic);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ user_id: getUserId(), tv_id: tvId, ...body }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as { progress?: TvProgress };
      if (!data.progress) throw new Error("empty progress response");
      setLoaded(data.progress);
      onChange(data.progress);
      publishProgress(tvId, data.progress);
    } catch {
      setLoaded(previous);
      onChange(previous);
      publishProgress(tvId, previous);
      setError("Не удалось сохранить прогресс. Изменения отменены.");
    } finally {
      setSaving(false);
    }
  };

  const toggleSeason = async (seasonNumber: number) => {
    if (open === seasonNumber) {
      setOpen(null);
      return;
    }
    setOpen(seasonNumber);
    const season = loaded.seasons.find((item) => item.season_number === seasonNumber);
    if (season?.loaded && season.episodes.length > 0) return;
    setLoadingSeason(seasonNumber);
    try {
      const response = await fetch(
        `${API_BASE}/api/tv/season?tv_id=${tvId}&season_number=${seasonNumber}&user_id=${getUserId()}`,
        { headers: getAuthHeaders() },
      );
      const data = (await response.json()) as { season?: TvProgress["seasons"][number] };
      if (data.season) {
        setLoaded((current) =>
          current
            ? {
                ...current,
                seasons: current.seasons.map((item) =>
                  item.season_number === seasonNumber ? data.season! : item,
                ),
              }
            : current,
        );
      }
    } finally {
      setLoadingSeason(null);
    }
  };

  return (
    <div className="space-y-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-center justify-between text-xs text-zinc-300">
        <span className="font-semibold">
          Прогресс
          {loaded.state === "watching"
            ? " · Смотрю"
            : loaded.state === "caught_up"
              ? " · Всё вышедшее"
              : loaded.state === "completed"
                ? " · Завершён"
                : ""}
        </span>
        <span className="text-neon-cyan">
          {loaded.watched_episodes}/{loaded.available_episodes || loaded.known_episodes || 0} серий
        </span>
      </div>
      <button
        className={`w-full rounded-xl border px-3 py-2 text-left text-[11px] ${notifications ? "border-neon-green/40 bg-neon-green/10 text-neon-green" : "border-white/10 text-zinc-400"}`}
        onClick={async () => {
          const enabled = !notifications;
          const response = await fetch(`${API_BASE}/api/tv/notifications`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ user_id: getUserId(), tv_id: tvId, enabled }),
          });
          if (response.ok) setNotifications(enabled);
        }}
      >
        {notifications ? "🔔 Уведомления включены" : "🔕 Уведомлять о новых сериях"}
      </button>
      {loaded.next_episode ? (
        <div className="text-[11px] text-neon-cyan">
          Продолжить: S{String(loaded.next_episode.season_number).padStart(2, "0")}E
          {String(loaded.next_episode.episode_number).padStart(2, "0")} ·{" "}
          {loaded.next_episode.name || "Без названия"}
        </div>
      ) : loaded.caught_up ? (
        <div className="text-[11px] text-neon-green">
          {loaded.completed ? "Сериал полностью просмотрен" : "Все вышедшие серии просмотрены"}
          {loaded.next_air_date ? ` · Следующая: ${loaded.next_air_date}` : ""}
        </div>
      ) : null}
      {loaded.seasons.map((season) => {
        const isOpen = open === season.season_number;
        const seasonTotal = season.available_episode_count ?? season.episode_count;
        const complete =
          season.available_episode_count !== null &&
          season.available_episode_count > 0 &&
          season.available_episode_count === season.watched_episode_count;
        return (
          <div key={season.season_number} className="rounded-xl border border-white/5 bg-black/10">
            <div className="flex items-center gap-2 px-2 py-2">
              <button
                className="flex min-w-0 flex-1 items-center gap-2 text-left text-xs text-zinc-200"
                onClick={() => void toggleSeason(season.season_number)}
              >
                {isOpen ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
                <span className="truncate">Сезон {season.season_number}</span>
                <span className="text-zinc-500">
                  {season.watched_episode_count}/{seasonTotal}
                </span>
                {complete && <Check className="h-3.5 w-3.5 text-neon-green" />}
              </button>
              <button
                disabled={saving}
                className="min-h-9 rounded-lg border border-neon-cyan/30 px-2 py-1 text-[10px] text-neon-cyan"
                onClick={() =>
                  void update(`${API_BASE}/api/tv/season-progress`, {
                    season_number: season.season_number,
                    watched: !complete,
                  })
                }
              >
                {complete ? "Снять" : "Весь сезон"}
              </button>
            </div>
            {isOpen && loadingSeason === season.season_number ? (
              <div className="border-t border-white/5 px-3 py-3 text-[11px] text-zinc-500">
                Загружаю серии…
              </div>
            ) : (
              isOpen && (
                <div className="grid grid-cols-2 gap-1.5 border-t border-white/5 p-2">
                  {season.episodes.map((episode) => {
                    const aired = Boolean(
                      episode.air_date && new Date(`${episode.air_date}T23:59:59`) <= new Date(),
                    );
                    return (
                      <button
                        key={episode.episode_number}
                        disabled={!aired || saving}
                        className={`min-h-10 min-w-0 rounded-lg border px-2 py-1.5 text-left text-[10px] ${episode.watched ? "border-neon-green/40 bg-neon-green/10 text-neon-green" : "border-white/10 text-zinc-300"} ${!aired ? "cursor-not-allowed opacity-40" : ""}`}
                        onClick={() =>
                          void update(`${API_BASE}/api/tv/episode-progress`, {
                            season_number: season.season_number,
                            episode_number: episode.episode_number,
                            watched: !episode.watched,
                          })
                        }
                      >
                        <span className="font-semibold">
                          E{String(episode.episode_number).padStart(2, "0")}
                        </span>{" "}
                        <span className="break-words">{episode.name || "Серия"}</span>
                        {!aired && <span className="block text-[9px]">ещё не вышла</span>}
                      </button>
                    );
                  })}
                </div>
              )
            )}
          </div>
        );
      })}
      {error && (
        <div className="rounded-xl border border-neon-red/30 bg-neon-red/10 px-3 py-2 text-[11px] text-neon-red">
          {error}
        </div>
      )}
    </div>
  );
}

function applyOptimisticProgress(
  progress: TvProgress,
  body: { season_number: number; episode_number?: number; watched: boolean },
): TvProgress {
  const seasons = progress.seasons.map((season) => {
    if (season.season_number !== body.season_number) return season;
    const episodes = season.episodes.map((episode) =>
      body.episode_number == null || episode.episode_number !== body.episode_number
        ? episode
        : { ...episode, watched: body.watched },
    );
    const aired = episodes.filter(
      (episode) => episode.air_date && new Date(`${episode.air_date}T23:59:59`) <= new Date(),
    );
    const watched =
      body.episode_number == null
        ? body.watched
          ? aired.length
          : 0
        : aired.filter((episode) => episode.watched).length;
    return { ...season, episodes, watched_episode_count: watched };
  });
  const available = seasons.reduce((sum, season) => sum + (season.available_episode_count ?? 0), 0);
  const watched = seasons.reduce((sum, season) => sum + season.watched_episode_count, 0);
  const availableEpisodes = available || progress.available_episodes;
  const nextEpisode = seasons
    .flatMap((season) => season.episodes)
    .filter((episode) => episode.air_date && new Date(`${episode.air_date}T23:59:59`) <= new Date())
    .filter((episode) => !episode.watched)
    .sort(
      (a, b) =>
        (a.season_number ?? 0) - (b.season_number ?? 0) || a.episode_number - b.episode_number,
    )[0];
  return {
    ...progress,
    seasons,
    available_episodes: availableEpisodes,
    watched_episodes: watched,
    next_episode: nextEpisode ?? (watched === availableEpisodes ? null : progress.next_episode),
    caught_up: availableEpisodes > 0 && watched === availableEpisodes,
    completed: progress.completed && availableEpisodes > 0 && watched === availableEpisodes,
    state:
      availableEpisodes > 0 && watched === availableEpisodes
        ? "caught_up"
        : watched > 0
          ? "watching"
          : progress.state,
  };
}
