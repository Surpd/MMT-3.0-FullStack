import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Trophy, RotateCcw } from "lucide-react";
import { MOVIES, type Movie } from "@/lib/movies";
import { store, useStore } from "@/lib/store";
import { tgHaptic, tgNotify, tgSendData } from "@/lib/telegram";

type Question = {
  movie: Movie;
  options: Movie[];
};

const QUESTION_COUNT = 5;

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function buildQuiz(): Question[] {
  const picks = shuffle(MOVIES).slice(0, QUESTION_COUNT);
  return picks.map((movie) => {
    const distractors = shuffle(MOVIES.filter((m) => m.id !== movie.id)).slice(0, 3);
    return { movie, options: shuffle([movie, ...distractors]) };
  });
}

export function QuizTab() {
  const highScore = useStore((s) => s.quizHighScore);
  const [questions, setQuestions] = useState<Question[]>(() => buildQuiz());
  const [idx, setIdx] = useState(0);
  const [score, setScore] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const q = questions[idx];
  const progress = useMemo(() => ((idx + (picked ? 1 : 0)) / questions.length) * 100, [idx, picked, questions.length]);

  const choose = (movieId: string) => {
    if (picked) return;
    setPicked(movieId);
    const correct = movieId === q.movie.id;
    if (correct) {
      setScore((s) => s + 1);
      tgNotify("success");
    } else {
      tgNotify("error");
    }
    tgHaptic("medium");

    setTimeout(() => {
      if (idx + 1 >= questions.length) {
        const finalScore = score + (correct ? 1 : 0);
        store.setQuizScore(finalScore);
        tgSendData({ action: "quiz_complete", score: finalScore, total: questions.length });
        setDone(true);
      } else {
        setIdx((i) => i + 1);
        setPicked(null);
      }
    }, 900);
  };

  const restart = () => {
    setQuestions(buildQuiz());
    setIdx(0);
    setScore(0);
    setPicked(null);
    setDone(false);
  };

  if (done) {
    return <ResultScreen score={score} total={questions.length} highScore={highScore} onRestart={restart} />;
  }

  return (
    <div className="flex flex-col h-full px-5 pt-4 pb-4">
      {/* Progress */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
          <motion.div
            className="h-full bg-neon-cyan shadow-[0_0_10px_rgba(34,211,238,0.6)]"
            animate={{ width: `${progress}%` }}
            transition={{ type: "spring", stiffness: 200, damping: 30 }}
          />
        </div>
        <div className="font-mono text-[11px] text-zinc-400 tabular-nums">
          {idx + 1}/{questions.length}
        </div>
      </div>

      <div className="text-[10px] uppercase tracking-[0.25em] text-neon-cyan font-semibold mb-2">
        Plot Clue
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={q.movie.id}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -16 }}
          transition={{ duration: 0.25 }}
          className="rounded-2xl bg-zinc-900/70 border border-white/10 p-5 mb-5"
        >
          <p className="text-zinc-200 text-sm leading-relaxed">{q.movie.plot}</p>
        </motion.div>
      </AnimatePresence>

      <div className="grid grid-cols-1 gap-2.5">
        {q.options.map((opt) => {
          const isCorrect = picked && opt.id === q.movie.id;
          const isWrong = picked === opt.id && opt.id !== q.movie.id;
          return (
            <motion.button
              key={opt.id}
              whileTap={{ scale: 0.98 }}
              onClick={() => choose(opt.id)}
              disabled={!!picked}
              className={`relative h-14 px-4 rounded-2xl border text-left text-sm font-semibold flex items-center justify-between transition-all ${
                isCorrect
                  ? "bg-neon-green/15 border-neon-green text-neon-green shadow-[0_0_20px_rgba(57,255,20,0.25)]"
                  : isWrong
                    ? "bg-neon-red/15 border-neon-red text-neon-red"
                    : "bg-zinc-900/60 border-white/10 text-zinc-200 hover:border-white/25"
              }`}
            >
              <span>{opt.title}</span>
              <span className="text-[10px] font-mono opacity-60">{opt.year}</span>
            </motion.button>
          );
        })}
      </div>

      <div className="mt-auto pt-4 flex items-center justify-between text-[11px] font-mono text-zinc-500">
        <span>Score: <span className="text-neon-cyan">{score}</span></span>
        <span>High: <span className="text-zinc-300">{highScore}</span></span>
      </div>
    </div>
  );
}

function ResultScreen({
  score,
  total,
  highScore,
  onRestart,
}: {
  score: number;
  total: number;
  highScore: number;
  onRestart: () => void;
}) {
  const pct = Math.round((score / total) * 100);
  const isNew = score >= highScore && score > 0;
  return (
    <div className="flex flex-col h-full items-center justify-center px-8 text-center">
      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 280, damping: 20 }}
        className="size-24 rounded-full bg-neon-cyan/15 border border-neon-cyan/40 flex items-center justify-center mb-6 shadow-[0_0_50px_rgba(34,211,238,0.3)]"
      >
        <Trophy className="w-11 h-11 text-neon-cyan" />
      </motion.div>
      <div className="font-cinematic text-5xl text-white tracking-wide leading-none mb-2">
        {pct === 100 ? "FLAWLESS" : pct >= 60 ? "WELL DONE" : "KEEP GOING"}
      </div>
      <div className="text-zinc-400 text-sm mb-6">
        You scored <span className="text-neon-cyan font-bold">{score}</span> out of {total}
      </div>
      {isNew && (
        <div className="mb-6 px-4 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/40 text-neon-green text-[11px] font-bold uppercase tracking-wider">
          New high score
        </div>
      )}
      <button
        onClick={onRestart}
        className="h-12 px-6 rounded-2xl bg-neon-cyan text-asphalt font-bold uppercase tracking-wider text-sm flex items-center gap-2 active:scale-95 transition shadow-[0_0_30px_rgba(34,211,238,0.35)]"
      >
        <RotateCcw className="w-4 h-4" /> Play Again
      </button>
    </div>
  );
}
