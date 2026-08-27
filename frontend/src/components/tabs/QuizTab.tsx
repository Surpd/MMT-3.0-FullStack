import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Award,
  ArrowLeft,
  CalendarDays,
  Check,
  Film,
  Library,
  Loader2,
  RotateCcw,
  X,
} from "lucide-react";
import { tgHaptic } from "@/lib/telegram";
import {
  fetchQuizSession,
  fetchQuizMeta,
  prewarmQuiz,
  postQuizSessionAnswer,
  type QuizMode,
  type QuizSession,
} from "@/lib/api";

type Screen = "home" | "question" | "result";
type AnswerState = {
  selected: string;
  correct: string;
  isCorrect: boolean;
  message: string;
  pending?: boolean;
};
type QuizResult = {
  correct: number;
  total: number;
  accuracy: number;
  score: number;
  best_combo: number;
  earned_xp: number;
};

const MODE_INFO: Record<QuizMode, { title: string; description: string; Icon: typeof Film }> = {
  cinema: { title: "Киноквиз", description: "Общие вопросы о фильмах и сериалах", Icon: Film },
  library: {
    title: "Моя библиотека",
    description: "Проверьте, насколько хорошо помните свою коллекцию",
    Icon: Library,
  },
  daily: {
    title: "Daily",
    description: "7 одинаковых вопросов для всех сегодня",
    Icon: CalendarDays,
  },
};

export function QuizTab() {
  const [screen, setScreen] = useState<Screen>("home");
  const [mode, setMode] = useState<QuizMode>("cinema");
  const [session, setSession] = useState<QuizSession | null>(null);
  const [meta, setMeta] = useState<Awaited<ReturnType<typeof fetchQuizMeta>>>(null);
  const [answer, setAnswer] = useState<AnswerState | null>(null);
  const [score, setScore] = useState(0);
  const [combo, setCombo] = useState(0);
  const [bestCombo, setBestCombo] = useState(0);
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startingMode, setStartingMode] = useState<QuizMode | null>(null);
  const [startedAt, setStartedAt] = useState(Date.now());
  const [imageState, setImageState] = useState<"loading" | "ready" | "error">("loading");
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchQuizMeta().then((nextMeta) => {
      if (cancelled) return;
      setMeta(nextMeta);
      if (!nextMeta) setError("Не удалось загрузить данные квиза. Попробуйте ещё раз.");
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!meta) return;
    const timer = window.setTimeout(() => void prewarmQuiz("cinema"), 250);
    return () => {
      window.clearTimeout(timer);
    };
  }, [meta]);

  useEffect(() => {
    setImageState(session?.questions[currentIndex]?.poster_url ? "loading" : "error");
  }, [session, currentIndex]);

  const startMode = async (nextMode: QuizMode) => {
    if (startingMode) return;
    setError(null);
    setMode(nextMode);
    setStartingMode(nextMode);
    if (nextMode === "library" && !meta?.library_unlocked) {
      setStartingMode(null);
      setError(`Добавьте ещё ${meta?.remaining ?? 20} произведений, чтобы открыть режим.`);
      return;
    }
    if (nextMode === "daily" && meta?.daily_status === "completed") {
      setStartingMode(null);
      setError("Сегодняшняя попытка уже использована.");
      return;
    }
    const next = await fetchQuizSession(nextMode);
    setStartingMode(null);
    if (!next) {
      setError("Не удалось подготовить сессию. Попробуйте ещё раз.");
      return;
    }
    if (next.locked) {
      if (next.daily_status === "completed") setError("Сегодняшняя попытка уже использована.");
      else setError(`Добавьте ещё ${next.remaining ?? 0} произведений, чтобы открыть режим.`);
      return;
    }
    setSession(next);
    setScore(0);
    setCombo(0);
    setBestCombo(0);
    setAnswer(null);
    setQuizResult(null);
    setCurrentIndex(0);
    setStartedAt(Date.now());
    setScreen("question");
  };

  const resetToHome = () => {
    setScreen("home");
    setSession(null);
    setAnswer(null);
    setQuizResult(null);
    setError(null);
  };

  const chooseAnswer = async (option: string) => {
    if (!session?.session_id || answer || submitting) return;
    const question = session.questions[currentIndex];
    if (!question) return;
    setSubmitting(true);
    setError(null);
    setAnswer({
      selected: option,
      correct: "",
      isCorrect: false,
      message: "Проверяем ответ…",
      pending: true,
    });
    tgHaptic("medium");
    const result = await postQuizSessionAnswer(
      session.session_id,
      question.id,
      option,
      Date.now() - startedAt,
    );
    setSubmitting(false);
    if (!result) {
      setAnswer(null);
      setError("Не удалось проверить ответ. Попробуйте ещё раз.");
      return;
    }
    setAnswer({
      selected: option,
      correct: result.correct_answer,
      isCorrect: result.is_correct,
      message: result.message,
      pending: false,
    });
    setScore(result.score);
    setCombo(result.combo);
    setBestCombo(result.best_combo);
    if (result.result) setQuizResult(result.result);
    window.setTimeout(() => {
      if (result.complete) setScreen("result");
      else {
        setAnswer(null);
        setStartedAt(Date.now());
        setCurrentIndex((value) => value + 1);
      }
    }, 850);
  };

  if (loading) return <CenteredState label="Загружаем квиз…" />;
  if (screen === "home") {
    return (
      <div className="flex h-full flex-col overflow-y-auto px-5 pb-6 pt-5">
        <div className="mb-5">
          <div className="text-[10px] font-bold tracking-[.25em] text-neon-cyan">
            MY MOVIE TRACKER
          </div>
          <h1 className="font-cinematic text-3xl tracking-wide text-white">КВИЗ</h1>
          <p className="mt-1 text-sm text-zinc-500">Выберите режим и проверьте свои знания.</p>
        </div>
        <div className="space-y-3">
          {(Object.keys(MODE_INFO) as QuizMode[]).map((key) => {
            const item = MODE_INFO[key];
            const locked = key === "library" && !meta?.library_unlocked;
            const Icon = item.Icon;
            return (
              <button
                key={key}
                onClick={() => void startMode(key)}
                disabled={locked || Boolean(startingMode)}
                aria-disabled={locked}
                className={`w-full rounded-2xl border p-4 text-left transition ${locked ? "border-white/8 bg-zinc-900/35" : "border-white/10 bg-zinc-900/65 active:scale-[.99]"}`}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${locked ? "bg-white/5 text-zinc-600" : "bg-neon-cyan/10 text-neon-cyan"}`}
                  >
                    <Icon className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span
                      className={`block text-sm font-bold ${locked ? "text-zinc-500" : "text-white"}`}
                    >
                      {item.title}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-zinc-500">
                      {item.description}
                    </span>
                    {locked && (
                      <span className="mt-2 block text-[11px] font-semibold text-zinc-400">
                        {meta?.library_count ?? 0} / 20 · ещё {meta?.remaining ?? 20}
                      </span>
                    )}
                    {key === "daily" && meta?.daily_status === "completed" && (
                      <span className="mt-2 block text-[11px] font-semibold text-zinc-500">
                        Сегодня уже пройдено
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-600">
                    {key === "daily" ? "7" : "10"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
        {error && <InlineError message={error} onRetry={() => setError(null)} />}
        <div className="mt-auto pt-8 text-center text-[11px] text-zinc-600">
          Правильный ответ и результат проверяются на сервере.
        </div>
      </div>
    );
  }

  if (screen === "result" && session) {
    const lastResult = quizResult || {
      correct: 0,
      total: session.questions.length,
      accuracy: 0,
      score,
      best_combo: bestCombo,
      earned_xp: 0,
    };
    return (
      <div className="flex h-full flex-col overflow-y-auto px-5 pb-6 pt-5">
        <button
          onClick={resetToHome}
          className="mb-8 flex w-fit items-center gap-2 text-xs font-bold text-zinc-400"
        >
          <ArrowLeft className="size-4" /> Все режимы
        </button>
        <div className="text-center">
          <Award className="mx-auto mb-3 size-10 text-neon-cyan" />
          <div className="text-[10px] font-bold tracking-[.25em] text-neon-cyan">
            СЕССИЯ ЗАВЕРШЕНА
          </div>
          <h2 className="mt-2 font-cinematic text-5xl text-white">
            {lastResult.correct} / {lastResult.total}
          </h2>
          <div className="mt-1 text-sm text-zinc-500">точность {lastResult.accuracy}%</div>
        </div>
        <div className="mt-8 grid grid-cols-3 divide-x divide-white/10 rounded-2xl border border-white/8 bg-zinc-900/55 py-4">
          <ResultStat label="SCORE" value={lastResult.score} />
          <ResultStat label="КОМБО" value={lastResult.best_combo} />
          <ResultStat label="XP" value={`+${lastResult.earned_xp}`} />
        </div>
        <button
          onClick={() => void startMode(mode)}
          className="mt-6 h-12 w-full rounded-2xl bg-neon-cyan font-bold text-asphalt active:scale-[.98]"
        >
          Пройти ещё раз
        </button>
        <button
          onClick={resetToHome}
          className="mt-3 h-12 w-full rounded-2xl border border-white/10 bg-zinc-900/70 text-sm font-bold text-zinc-300"
        >
          К режимам
        </button>
      </div>
    );
  }

  const question = session?.questions[currentIndex];
  if (!session || !question)
    return <CenteredState label="Сессия недоступна" error={error} onRetry={resetToHome} />;
  return (
    <div className="flex h-full flex-col overflow-hidden px-5 pb-6 pt-5">
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={resetToHome}
          className="flex items-center gap-1 text-xs font-bold text-zinc-500"
        >
          <ArrowLeft className="size-4" /> Выйти
        </button>
        <span className="text-sm font-bold text-zinc-300">
          {currentIndex + 1} / {session.questions.length}
        </span>
        <span className="text-sm font-bold text-neon-cyan">{score}</span>
      </div>
      <div className="mb-4 h-1 rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-neon-cyan transition-all"
          style={{ width: `${((currentIndex + 1) / session.questions.length) * 100}%` }}
        />
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={question.id}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          className="flex min-h-0 flex-1 flex-col"
        >
          {question.poster_url && imageState !== "error" && (
            <div className="relative mx-auto mb-4 h-36 w-full max-w-[18rem] overflow-hidden rounded-xl bg-white/5">
              {imageState === "loading" && (
                <div className="absolute inset-0 animate-pulse bg-white/5" />
              )}
              <img
                src={question.poster_url}
                alt=""
                onLoad={() => setImageState("ready")}
                onError={() => setImageState("error")}
                className={`h-full w-full object-cover transition-opacity ${imageState === "ready" ? "opacity-100" : "opacity-0"}`}
              />
            </div>
          )}
          <div className="mb-5 flex-1 rounded-2xl border border-white/8 bg-zinc-900/55 p-5 text-center">
            <div className="mb-3 text-[10px] font-bold uppercase tracking-[.2em] text-zinc-600">
              {question.difficulty}
            </div>
            <p className="text-sm font-medium leading-relaxed text-zinc-100">{question.question}</p>
          </div>
          {combo > 1 && (
            <div className="mb-3 text-center text-xs font-semibold text-neon-cyan">
              Комбо {combo}
            </div>
          )}
          <div className="space-y-2.5">
            {question.options.map((option) => {
              const selected = answer?.selected === option;
              const correct = answer?.correct === option;
              const stateClass = answer
                ? answer.pending && selected
                  ? "border-neon-cyan/60 bg-neon-cyan/10 text-neon-cyan"
                  : correct
                    ? "border-neon-green/60 bg-neon-green/10 text-neon-green"
                    : selected
                      ? "border-neon-red/60 bg-neon-red/10 text-neon-red"
                      : "border-white/5 bg-zinc-900/30 text-zinc-600"
                : "border-white/10 bg-zinc-900/70 text-zinc-200";
              return (
                <button
                  key={option}
                  disabled={Boolean(answer) || submitting}
                  onClick={() => void chooseAnswer(option)}
                  className={`flex min-h-12 w-full items-center gap-3 rounded-xl border px-4 text-left text-sm font-semibold transition ${stateClass}`}
                >
                  {answer?.pending && selected ? (
                    <Loader2 className="size-4 shrink-0 animate-spin" />
                  ) : answer && correct ? (
                    <Check className="size-4 shrink-0" />
                  ) : answer && selected ? (
                    <X className="size-4 shrink-0" />
                  ) : (
                    <span className="size-4 shrink-0 rounded-full border border-current/40" />
                  )}
                  <span>{option}</span>
                </button>
              );
            })}
          </div>
          {answer && (
            <div
              className={`mt-4 text-center text-xs font-semibold ${answer.isCorrect ? "text-neon-green" : "text-neon-red"}`}
            >
              {answer.message}
            </div>
          )}
          {error && <InlineError message={error} onRetry={() => setError(null)} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function ResultStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <div className="text-[9px] font-bold tracking-wider text-zinc-500">{label}</div>
      <div className="mt-1 font-cinematic text-2xl text-white">{value}</div>
    </div>
  );
}

function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mt-4 rounded-xl border border-neon-red/25 bg-neon-red/5 p-3 text-center text-xs text-neon-red">
      <div>{message}</div>
      <button onClick={onRetry} className="mt-2 inline-flex items-center gap-1 font-bold">
        <RotateCcw className="size-3" /> Повторить
      </button>
    </div>
  );
}

function CenteredState({
  label,
  error,
  onRetry,
}: {
  label: string;
  error?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <Loader2 className="mb-4 size-7 animate-spin text-neon-cyan" />
      <div className="text-sm font-semibold text-zinc-400">{error || label}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-xs font-bold text-zinc-300"
        >
          <RotateCcw className="size-3" /> Вернуться
        </button>
      )}
    </div>
  );
}
