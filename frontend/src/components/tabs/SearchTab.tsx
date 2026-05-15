import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Search, Star } from "lucide-react";
import { MOVIES, ALL_GENRES, type Movie } from "@/lib/movies";

const EXTRA_FILTERS = ["Top Rated", "2024", "2023", "Recent"];

export function SearchTab({ onOpen }: { onOpen: (m: Movie) => void }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState<string | null>(null);

  const results = useMemo(() => {
    let list = MOVIES;
    if (q.trim()) {
      const needle = q.toLowerCase();
      list = list.filter(
        (m) =>
          m.title.toLowerCase().includes(needle) ||
          m.plot.toLowerCase().includes(needle) ||
          m.director.toLowerCase().includes(needle)
      );
    }
    if (active) {
      if (active === "Top Rated") list = list.filter((m) => m.rating >= 8.3);
      else if (/^\d{4}$/.test(active))
        list = list.filter((m) => String(m.year) === active);
      else if (active === "Recent")
        list = list.filter((m) => m.year >= 2020);
      else list = list.filter((m) => m.genres.includes(active));
    }
    return list;
  }, [q, active]);

  const chips = [...EXTRA_FILTERS, ...ALL_GENRES];

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-4 pb-3 space-y-3 shrink-0">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by title or description..."
            className="w-full h-12 pl-11 pr-4 rounded-2xl bg-zinc-900/80 border border-white/10 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-neon-cyan/50 focus:ring-2 focus:ring-neon-cyan/20 transition"
          />
        </div>
        <div className="flex gap-2 overflow-x-auto scrollbar-hide -mx-5 px-5">
          {chips.map((c) => {
            const on = active === c;
            return (
              <button
                key={c}
                onClick={() => setActive(on ? null : c)}
                className={`shrink-0 px-3.5 h-8 rounded-full text-[11px] font-semibold uppercase tracking-wider border transition ${
                  on
                    ? "bg-neon-cyan text-asphalt border-neon-cyan shadow-[0_0_20px_rgba(34,211,238,0.4)]"
                    : "bg-zinc-900/60 text-zinc-300 border-white/10 hover:border-white/20"
                }`}
              >
                {c}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 pb-4">
        {results.length === 0 ? (
          <div className="text-center text-zinc-500 text-sm pt-16">
            No movies match.
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            {results.map((m, i) => (
              <PosterTile key={m.id} movie={m} onOpen={onOpen} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PosterTile({
  movie,
  onOpen,
  index,
}: {
  movie: Movie;
  onOpen: (m: Movie) => void;
  index: number;
}) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.025, 0.3) }}
      onClick={() => onOpen(movie)}
      className="relative aspect-[2/3] rounded-xl overflow-hidden bg-zinc-900 border border-white/5 group"
    >
      <img
        src={movie.poster}
        alt={movie.title}
        className="w-full h-full object-cover transition-transform group-active:scale-95"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition" />
      <div className="absolute bottom-1.5 left-1.5 right-1.5 flex items-center gap-1 text-[10px]">
        <Star className="w-2.5 h-2.5 fill-neon-cyan text-neon-cyan" />
        <span className="text-white font-semibold">{movie.rating}</span>
      </div>
    </motion.button>
  );
}
