import { useEffect } from "react";
import { motion } from "framer-motion";
import { X, Star, Play } from "lucide-react";
import type { Movie } from "@/lib/movies";
import { tgHaptic, tgSendData } from "@/lib/telegram";

export function DetailModal({ movie, onClose }: { movie: Movie; onClose: () => void }) {
  useEffect(() => {
    const orig = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = orig;
    };
  }, []);

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
        <div className="relative h-72 shrink-0">
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
            <h2 className="font-cinematic text-4xl text-white tracking-wide leading-none">
              {movie.title}
            </h2>
            <div className="flex items-center gap-3 text-zinc-300 text-xs mt-2">
              <span>{movie.year}</span>
              <span className="size-1 bg-zinc-600 rounded-full" />
              <span className="text-neon-cyan flex items-center gap-1">
                <Star className="w-3 h-3 fill-neon-cyan" /> {movie.rating}
              </span>
              <span className="size-1 bg-zinc-600 rounded-full" />
              <span>{movie.runtime}m</span>
            </div>
          </div>
        </div>

        <div className="mobile-scroll p-5 space-y-4">
          <div className="flex flex-wrap gap-2">
            {movie.genres.map((g) => (
              <span
                key={g}
                className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wider bg-white/5 border border-white/10 rounded-full text-zinc-300"
              >
                {g}
              </span>
            ))}
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-semibold mb-1">
              Director
            </div>
            <div className="text-zinc-200 text-sm">{movie.director}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-semibold mb-1">
              Plot
            </div>
            <p className="text-zinc-300 text-sm leading-relaxed">{movie.plot}</p>
          </div>
          <button
            onClick={() => {
              tgHaptic("light");
              tgSendData({ action: "trailer", movie_id: movie.id });
            }}
            className="w-full mt-2 h-12 rounded-2xl bg-neon-cyan text-asphalt font-bold uppercase tracking-wider text-sm flex items-center justify-center gap-2 shadow-[0_0_30px_rgba(34,211,238,0.35)] active:scale-[0.98] transition"
          >
            <Play className="w-4 h-4 fill-asphalt" /> Watch Trailer
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
