import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Heart, Trophy, RotateCcw, Loader2, Flame } from "lucide-react";
import { tgHaptic } from "@/lib/telegram";
import { fetchStats, type UserStats, fetchQuizQuestion, postQuizAnswer, type QuizData } from "@/lib/api";

export function QuizTab() {
  const [currentQuiz, setCurrentQuiz] = useState<QuizData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lives, setLives] = useState(3);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadQuestion = async () => {
    setLoading(true);
    setPicked(null);
    setError(null);

    const q = await fetchQuizQuestion();
    setCurrentQuiz(q);
    if (!q) {
      setError("Не удалось загрузить вопрос");
    }
    setLoading(false);
  };

  useEffect(() => {
    void fetchStats().then(setStats);
    void loadQuestion();
  }, []);

  const handlePick = async (opt: string) => {
    if (picked || !currentQuiz) return;
    setPicked(opt);

    const isCorrect = opt === currentQuiz.correct;
    const nextLives = isCorrect ? lives : lives - 1;

    tgHaptic("medium");

    if (!isCorrect) {
      setLives((l) => l - 1);
    }

    const res = await postQuizAnswer(isCorrect);
    if (res) {
      setStats(res.stats);
      setMsg(res.message);
    }

    setTimeout(() => {
      setMsg("");
      if (!isCorrect && nextLives <= 0) return;
      void loadQuestion();
    }, 2000);
  };

  if (lives <= 0) {
    return (
      <div className="flex flex-col h-full items-center justify-center px-8 text-center">
        <Trophy className="w-16 h-16 text-neon-red mb-4" />
        <div className="font-cinematic text-4xl text-white mb-2">ИГРА ОКОНЧЕНА</div>
        <div className="text-zinc-400 text-sm mb-6">
          Ваш опыт: <span className="text-neon-cyan font-bold">{stats?.points || 0} XP</span>
        </div>
        <button
          onClick={() => {
            setLives(3);
            setMsg("");
            void loadQuestion();
          }}
          className="h-12 px-8 rounded-2xl bg-white text-black font-bold uppercase tracking-wider text-sm active:scale-95 transition"
        >
          Играть еще
        </button>
      </div>
    );
  }

  if (error && !loading && !currentQuiz) {
    return (
      <div className="flex flex-col h-full items-center justify-center px-8 text-center">
        <div className="size-20 rounded-full bg-neon-red/10 border border-neon-red/30 flex items-center justify-center mb-5">
          <Trophy className="w-9 h-9 text-neon-red" />
        </div>
        <div className="font-cinematic text-4xl text-white tracking-wide leading-none mb-3">
          ОШИБКА
        </div>
        <div className="text-zinc-400 text-sm mb-6">{error}</div>
        <button
          onClick={() => void loadQuestion()}
          className="h-12 px-8 rounded-2xl bg-white text-black font-bold uppercase tracking-wider text-sm flex items-center justify-center gap-2 active:scale-95 transition"
        >
          <RotateCcw className="w-4 h-4" /> Попробовать еще раз
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-5 pt-4 pb-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1">
          {[...Array(3)].map((_, i) => (
            <Heart
              key={i}
              className={`w-5 h-5 ${
                i < lives ? "fill-neon-red text-neon-red" : "fill-zinc-800 text-zinc-800"
              }`}
            />
          ))}
        </div>
        <div className="flex items-center gap-2 bg-zinc-900 px-3 py-1.5 rounded-full border border-white/10">
          <Flame
            className={`w-4 h-4 ${
              stats?.current_streak && stats.current_streak >= 3 ? "text-amber-500 fill-amber-500" : "text-zinc-500"
            }`}
          />
          <span className="text-[11px] font-bold text-white">{stats?.current_streak || 0}</span>
        </div>
      </div>

      <div className="flex-1 px-5 pb-6 flex flex-col min-h-0">
        {loading || !currentQuiz ? (
          <div className="flex-1 flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 text-neon-cyan animate-spin mb-4" />
            <div className="text-zinc-500 text-sm font-semibold uppercase tracking-widest animate-pulse">
              Генерируем вопрос...
            </div>
            {error && <div className="text-zinc-500 text-xs mt-3">{error}</div>}
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={currentQuiz.question}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex-1 flex flex-col min-h-0"
            >
              <div className="flex-1 relative min-h-0 my-4 bg-zinc-900/40 rounded-2xl border border-white/5 overflow-hidden flex flex-col">
                <div className="flex-1 overflow-y-auto p-4 flex items-center">
                  <p className="text-zinc-200 text-[15px] leading-relaxed text-center font-medium italic m-auto">
                    "{currentQuiz.question}"
                  </p>
                </div>
              </div>

              <div className="space-y-3 shrink-0">
                {currentQuiz.options.map((opt) => {
                  const isPicked = picked === opt;
                  const isCorrect = opt === currentQuiz.correct;
                  const showResult = picked !== null;

                  let bg = "bg-zinc-900/80 border-white/10";
                  if (showResult) {
                    if (isCorrect) bg = "bg-neon-green/20 border-neon-green/50 text-neon-green shadow-[0_0_20px_rgba(57,255,20,0.15)]";
                    else if (isPicked) bg = "bg-neon-red/20 border-neon-red/50 text-neon-red shadow-[0_0_20px_rgba(255,0,85,0.15)]";
                    else bg = "bg-zinc-900/40 border-white/5 opacity-50";
                  } else if (isPicked) {
                    bg = "bg-neon-cyan/20 border-neon-cyan text-neon-cyan";
                  }

                  return (
                    <button
                      key={opt}
                      onClick={() => void handlePick(opt)}
                      disabled={picked !== null}
                      className={`w-full p-4 rounded-2xl border text-sm font-semibold transition-all duration-300 flex items-center justify-center text-center ${bg} ${picked === null ? "active:scale-[0.98]" : ""}`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>

              {msg && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-center font-bold text-sm mt-4 text-white shrink-0"
                >
                  {msg}
                </motion.div>
              )}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
