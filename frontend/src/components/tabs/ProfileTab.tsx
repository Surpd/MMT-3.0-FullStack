import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from "recharts";
import { Eye, Bookmark, Trophy, Loader2, Flame } from "lucide-react";
import { getTelegramUser } from "@/lib/telegram";
import { fetchLibrary, fetchStats, type UserStats } from "@/lib/api";

const COLORS = [
  "#22d3ee", // Неоновый циан
  "#39ff14", // Кислотный зеленый
  "#ff0055", // Неоновый красный
  "#a855f7", // Фиолетовый
  "#f59e0b", // Янтарный
  "#0ea5e9", // Светло-синий
  "#ec4899", // Розовый
  "#8b5cf6", // Лиловый
  "#10b981", // Изумрудный
  "#f97316", // Оранжевый
  "#6366f1", // Индиго
  "#14b8a6", // Бирюзовый
  "#f43f5e", // Малиновый
  "#84cc16", // Лаймовый
  "#eab308", // Желтый
  "#3b82f6", // Синий
  "#d946ef", // Фуксия
  "#ef4444", // Красный
  "#06b6d4", // Темный циан
  "#22c55e", // Зеленый
];

export function ProfileTab() {
  const user = getTelegramUser();

  const [loading, setLoading] = useState(true);
  const [genreData, setGenreData] = useState<{name: string, value: number}[]>([]);
  const [stats, setStats] = useState({
    watched: 0,
    wishlist: 0,
    hours: 0,
  });
  const [userStats, setUserStats] = useState<UserStats | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadStats() {
      try {
        const [liked, wanted, statsRes] = await Promise.all([
          fetchLibrary("liked", 1),
          fetchLibrary("watchlist", 1),
          fetchStats(),
        ]);

        if (!isMounted) return;

        let totalMins = 0;
        const genreCounts: Record<string, number> = {};

        liked.forEach((m) => {
          // Нормализация жанров: делаем первую букву большой, остальные маленькими
          if (m.genre_names) {
            m.genre_names.forEach((g) => {
              if (!g) return;
              const normalized = g.charAt(0).toUpperCase() + g.slice(1).toLowerCase();
              genreCounts[normalized] = (genreCounts[normalized] ?? 0) + 1;
            });
          }
          // Хронометраж
          if (m.runtime_mins) totalMins += m.runtime_mins;
        });

        // Сортируем жанры для графика
        const entries = Object.entries(genreCounts)
          .sort((a, b) => b[1] - a[1])
          .map(([name, value]) => ({ name, value }));

        setGenreData(entries);
        setStats({
          watched: liked.length,
          wishlist: wanted.length,
          hours: Math.floor(totalMins / 60),
        });
        setUserStats(statsRes);

      } catch (e) {
        console.error("Profile stats fetch failed:", e);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadStats();
    return () => { isMounted = false; };
  }, []);

  const displayName = user?.first_name || user?.username || "Cinephile";
  const handle = user?.username ? `@${user.username}` : "Telegram User";

  return (
    <div className="flex flex-col h-full overflow-y-auto px-5 pt-4 pb-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4 mb-6"
      >
        <div className="size-16 rounded-full p-0.5 bg-gradient-to-br from-neon-cyan to-neon-red shrink-0">
          <div className="size-full rounded-full overflow-hidden bg-zinc-900 flex items-center justify-center">
            {user?.photo_url ? (
              <img src={user.photo_url} alt="avatar" className="size-full object-cover" />
            ) : (
              <span className="font-cinematic text-2xl text-white">
                {displayName.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
        </div>
        <div className="min-w-0">
          <div className="font-cinematic text-2xl tracking-wide text-white truncate leading-none">
            {displayName}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <div className="text-zinc-500 text-xs truncate">{handle}</div>
            {userStats && (
              <div className="px-2 py-0.5 rounded-full bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan text-[10px] font-bold tracking-wider uppercase shrink-0">
                LVL {userStats.level} • {userStats.title}
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* Stat cards (Grid 2x2) */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatCard label="Смотрел" value={stats.watched} icon={<Eye className="w-4 h-4" />} color="cyan" loading={loading} />
        <StatCard label="В планах" value={stats.wishlist} icon={<Bookmark className="w-4 h-4" />} color="green" loading={loading} />
        <StatCard label="XP (Опыт)" value={userStats?.points || 0} icon={<Trophy className="w-4 h-4" />} color="purple" loading={loading} />
        <StatCard label="Рекорд (Стрик)" value={userStats?.best_streak || 0} icon={<Flame className="w-4 h-4" />} color="red" loading={loading} />
      </div>

      {/* Chart */}
      <div className="rounded-2xl bg-zinc-900/70 border border-white/10 p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-semibold">
              Аналитика
            </div>
            <div className="font-cinematic text-2xl text-white tracking-wide leading-none mt-1">
              ЛЮБИМЫЕ ЖАНРЫ
            </div>
          </div>
        </div>

        {loading ? (
          <div className="h-[220px] flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-neon-cyan animate-spin" />
          </div>
        ) : genreData.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-zinc-500 text-sm text-center">
            Свайпните пару фильмов, чтобы увидеть график.
          </div>
        ) : (
          <>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={genreData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    stroke="none"
                  >
                    {genreData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{
                      background: "rgba(9,9,11,0.95)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: "12px",
                      fontSize: "12px",
                      color: "#fff",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-4">
              {genreData.slice(0, 6).map((g, i) => (
                <div key={g.name} className="flex items-center gap-2 text-xs">
                  <span
                    className="size-2.5 rounded-sm shrink-0"
                    style={{ background: COLORS[i % COLORS.length] }}
                  />
                  <span className="text-zinc-300 truncate flex-1">{g.name}</span>
                  <span className="text-zinc-500 font-mono">{g.value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: "cyan" | "green" | "red" | "purple";
  loading: boolean;
}) {
  const map = {
    cyan: "text-neon-cyan border-neon-cyan/30 shadow-[0_0_20px_rgba(34,211,238,0.15)]",
    green: "text-neon-green border-neon-green/30 shadow-[0_0_20px_rgba(57,255,20,0.12)]",
    red: "text-neon-red border-neon-red/30 shadow-[0_0_20px_rgba(255,0,85,0.12)]",
    purple: "text-purple-400 border-purple-400/30 shadow-[0_0_20px_rgba(192,132,252,0.12)]",
  } as const;
  
  return (
    <motion.div
      whileHover={{ y: -2 }}
      className={`rounded-2xl bg-zinc-900/70 border ${map[color]} p-3.5 flex flex-col justify-between`}
    >
      <div className={`flex items-center gap-2 ${map[color].split(" ")[0]} mb-2`}>
        {icon}
        <span className="text-[9px] uppercase tracking-wider font-bold truncate">{label}</span>
      </div>
      <div className="font-cinematic text-4xl text-white tracking-wide leading-none truncate">
        {loading ? <Loader2 className="w-6 h-6 animate-spin mt-1" /> : value}
      </div>
    </motion.div>
  );
}
