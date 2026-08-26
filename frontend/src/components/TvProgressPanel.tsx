import { useEffect, useState } from "react";
import { Check, ChevronDown, ChevronRight } from "lucide-react";
import { API_BASE, getAuthHeaders, getUserId, type TvProgress } from "@/lib/api";

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
  const [notifications, setNotifications] = useState(false);
  const [loaded, setLoaded] = useState(progress);
  useEffect(() => {
    if (progress) {
      setLoaded(progress);
      setNotifications(Boolean(progress.notification_enabled));
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/api/tv/progress?tv_id=${tvId}&user_id=${getUserId()}`, { headers: getAuthHeaders() })
      .then((response) => response.json())
      .then((data: { progress?: TvProgress }) => {
        if (!cancelled && data.progress) {
          setLoaded(data.progress);
          setNotifications(Boolean(data.progress.notification_enabled));
        }
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [progress, tvId]);
  if (!loaded) return <div className="text-[11px] text-zinc-500">Загружаю сезоны…</div>;

  const update = async (url: string, body: object) => {
    const response = await fetch(url, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ user_id: getUserId(), tv_id: tvId, ...body }),
    });
    if (!response.ok) return;
    const data = (await response.json()) as { progress?: TvProgress };
    if (data.progress) {
      setLoaded(data.progress);
      onChange(data.progress);
    }
  };

  return (
    <div className="space-y-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-center justify-between text-xs text-zinc-300">
        <span className="font-semibold">Прогресс</span>
        <span className="text-neon-cyan">{loaded.watched_episodes}/{loaded.available_episodes}</span>
      </div>
      <button
        className={`w-full rounded-xl border px-3 py-2 text-left text-[11px] ${notifications ? "border-neon-green/40 bg-neon-green/10 text-neon-green" : "border-white/10 text-zinc-400"}`}
        onClick={async () => {
          const enabled = !notifications;
          const response = await fetch(`${API_BASE}/api/tv/notifications`, { method: "POST", headers: getAuthHeaders(), body: JSON.stringify({ user_id: getUserId(), tv_id: tvId, enabled }) });
          if (response.ok) setNotifications(enabled);
        }}
      >
        {notifications ? "🔔 Уведомления включены" : "🔕 Уведомлять о новых сериях"}
      </button>
      {loaded.next_episode ? (
        <div className="text-[11px] text-neon-cyan">
          Продолжить: S{String(loaded.next_episode.season_number).padStart(2, "0")}E{String(loaded.next_episode.episode_number).padStart(2, "0")} · {loaded.next_episode.name || "Без названия"}
        </div>
      ) : loaded.caught_up ? (
        <div className="text-[11px] text-neon-green">
          {loaded.completed ? "Сериал полностью просмотрен" : "Все вышедшие серии просмотрены"}
          {loaded.next_air_date ? ` · Следующая: ${loaded.next_air_date}` : ""}
        </div>
      ) : null}
      {loaded.seasons.map((season) => {
        const isOpen = open === season.season_number;
        const complete = season.available_episode_count > 0 && season.available_episode_count === season.watched_episode_count;
        return (
          <div key={season.season_number} className="rounded-xl border border-white/5 bg-black/10">
            <div className="flex items-center gap-2 px-2 py-2">
              <button className="flex min-w-0 flex-1 items-center gap-2 text-left text-xs text-zinc-200" onClick={() => setOpen(isOpen ? null : season.season_number)}>
                {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                <span className="truncate">Сезон {season.season_number}</span>
                <span className="text-zinc-500">{season.watched_episode_count}/{season.available_episode_count}</span>
                {complete && <Check className="h-3.5 w-3.5 text-neon-green" />}
              </button>
              <button
                className="rounded-lg border border-neon-cyan/30 px-2 py-1 text-[10px] text-neon-cyan"
                onClick={() => void update(`${API_BASE}/api/tv/season-progress`, { season_number: season.season_number, watched: !complete })}
              >
                {complete ? "Снять" : "Весь сезон"}
              </button>
            </div>
            {isOpen && (
              <div className="grid grid-cols-2 gap-1.5 border-t border-white/5 p-2">
                {season.episodes.filter((episode) => episode.air_date && new Date(`${episode.air_date}T23:59:59`) <= new Date()).map((episode) => (
                  <button
                    key={episode.episode_number}
                    className={`rounded-lg border px-2 py-1.5 text-left text-[10px] ${episode.watched ? "border-neon-green/40 bg-neon-green/10 text-neon-green" : "border-white/10 text-zinc-300"}`}
                    onClick={() => void update(`${API_BASE}/api/tv/episode-progress`, { season_number: season.season_number, episode_number: episode.episode_number, watched: !episode.watched })}
                  >
                    <span className="font-semibold">E{String(episode.episode_number).padStart(2, "0")}</span> {episode.name || "Серия"}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
