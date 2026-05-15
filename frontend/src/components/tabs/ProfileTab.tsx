import { useMemo } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Eye, Bookmark, Trophy } from "lucide-react";
import { MOVIES } from "@/lib/movies";
import { useStore } from "@/lib/store";
import { getTelegramUser } from "@/lib/telegram";

const COLORS = ["#22d3ee", "#39ff14", "#ff0055", "#a855f7", "#f59e0b", "#0ea5e9", "#ec4899"];

export function ProfileTab() {
  const statusMap = useStore((s) => s.status);
  const highScore = useStore((s) => s.quizHighScore);
  const user = getTelegramUser();

  const watched = useMemo(
    () => MOVIES.filter((m) => statusMap[m.id] === "watched"),
    [statusMap]
  );
  const wishlist = useMemo(
    () => MOVIES.filter((m) => statusMap[m.id] === "wishlist"),
    [statusMap]
  );

  const genreData = useMemo(() => {
    const counts: Record<string, number> = {};
    watched.forEach((m) => {
      m.genres.forEach((g) => {
        counts[g] = (counts[g] ?? 0) + 1;
      });
    });
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return entries.map(([name, value]) => ({ name, value }));
  }, [watched]);

  const displayName =
    user?.first_name ||
    user?.username ||
    "Cinephile";
  const handle = user?.username ? `@${user.username}` : "Telegram User";

  return (
    <div className="flex flex-col h-full overflow-y-auto px-5 pt-4 pb-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4 mb-6"
      >
        <div className="size-16 rounded-full p-0.5 bg-gradient-to-br from-neon-cyan to-neon-red">
          <div className="size-full rounded-full overflow-hidden bg-zinc-900 flex items-center justify-center">
            {user?.photo_url ? (
              // eslint-disable-next-line jsx-a11y/img-redundant-alt
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
          <div className="text-zinc-500 text-xs mt-1 truncate">{handle}</div>
        </div>
      </motion.div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-2.5 mb-6">
        <StatCard label="Watched" value={watched.length} icon={<Eye className="w-3.5 h-3.5" />} color="cyan" />
        <StatCard label="Wishlist" value={wishlist.length} icon={<Bookmark className="w-3.5 h-3.5" />} color="green" />
        <StatCard label="High Score" value={highScore} icon={<Trophy className="w-3.5 h-3.5" />} color="red" />
      </div>

      {/* Chart */}
      <div className="rounded-2xl bg-zinc-900/70 border border-white/10 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-semibold">
              Analytics
            </div>
            <div className="font-cinematic text-2xl text-white tracking-wide leading-none mt-1">
              FAVORITE GENRES
            </div>
          </div>
        </div>

        {genreData.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-zinc-500 text-sm">
            Watch a few movies to see your taste.
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
                  <Tooltip
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
                    className="size-2.5 rounded-sm"
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

      <div className="text-center text-[10px] uppercase tracking-[0.25em] text-zinc-600 font-semibold mt-6 pb-2">
        My Movie Tracker · v1.0
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: "cyan" | "green" | "red";
}) {
  const map = {
    cyan: "text-neon-cyan border-neon-cyan/30 shadow-[0_0_20px_rgba(34,211,238,0.15)]",
    green: "text-neon-green border-neon-green/30 shadow-[0_0_20px_rgba(57,255,20,0.12)]",
    red: "text-neon-red border-neon-red/30 shadow-[0_0_20px_rgba(255,0,85,0.12)]",
  } as const;
  return (
    <motion.div
      whileHover={{ y: -2 }}
      className={`rounded-2xl bg-zinc-900/70 border ${map[color]} p-3 flex flex-col`}
    >
      <div className={`flex items-center gap-1.5 ${map[color].split(" ")[0]}`}>
        {icon}
        <span className="text-[9px] uppercase tracking-wider font-bold">{label}</span>
      </div>
      <div className="font-cinematic text-3xl text-white tracking-wide mt-2 leading-none">
        {value}
      </div>
    </motion.div>
  );
}
