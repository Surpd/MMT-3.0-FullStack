import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Flame, Search, Library, Brain, User } from "lucide-react";
import { DiscoverTab } from "./tabs/DiscoverTab";
import { SearchTab } from "./tabs/SearchTab";
import { LibraryTab } from "./tabs/LibraryTab";
import { QuizTab } from "./tabs/QuizTab";
import { ProfileTab } from "./tabs/ProfileTab";
import { tgInit, tgHaptic } from "@/lib/telegram";
import type { Movie } from "@/lib/movies";
import { DetailModal } from "./DetailModal";
import { DeckProvider } from "@/lib/DeckContext";

type TabKey = "discover" | "search" | "library" | "quiz" | "profile";

const TABS: { key: TabKey; label: string; Icon: typeof Flame }[] = [
  { key: "discover", label: "Discover", Icon: Flame },
  { key: "search", label: "Search", Icon: Search },
  { key: "library", label: "Library", Icon: Library },
  { key: "quiz", label: "Quiz", Icon: Brain },
  { key: "profile", label: "Profile", Icon: User },
];

export function App() {
  const [tab, setTab] = useState<TabKey>("discover");
  const [openMovie, setOpenMovie] = useState<Movie | null>(null);
  const [globalSearchQuery, setGlobalSearchQuery] = useState("");

  useEffect(() => {
    tgInit();
    const tg = typeof window !== "undefined" ? (window as any).Telegram?.WebApp : null;
    if (tg) tg.expand();
  }, []);

  return (
    <DeckProvider>
    <div className="relative h-dvh w-full max-w-[480px] mx-auto bg-asphalt text-zinc-100 overflow-hidden flex flex-col">
      {/* Ambient glow */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-32 -left-32 size-[420px] bg-neon-red/10 blur-[120px] rounded-full" />
        <div className="absolute -bottom-32 -right-32 size-[420px] bg-neon-cyan/10 blur-[120px] rounded-full" />
      </div>

      {/* Tab content */}
      <div className="relative z-10 flex-1 min-h-0 pb-24">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18 }}
            className="h-full"
          >
            {tab === "discover" && <DiscoverTab />}
            {tab === "search" && (
              <SearchTab onOpen={setOpenMovie} initialQuery={globalSearchQuery} />
            )}
            {tab === "library" && (
              <LibraryTab
                onNavigateToSearch={(query) => {
                  setGlobalSearchQuery(query);
                  setTab("search");
                }}
              />
            )}
            {tab === "quiz" && <QuizTab />}
            {tab === "profile" && <ProfileTab />}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom tab bar — glassmorphism */}
      <nav className="fixed bottom-3 left-1/2 -translate-x-1/2 w-[calc(100%-24px)] max-w-[440px] z-30">
        <div className="glass-tabbar rounded-3xl border border-white/10 px-2 py-2 flex items-center justify-between shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)]">
          {TABS.map(({ key, label, Icon }) => {
            const active = tab === key;
            return (
              <button
                key={key}
                onClick={() => {
                  if (key !== tab) tgHaptic("light");
                  setTab(key);
                }}
                className="relative flex-1 h-14 flex flex-col items-center justify-center gap-0.5 group"
                aria-label={label}
              >
                {active && (
                  <motion.div
                    layoutId="tabbar-pill"
                    className="absolute inset-1 rounded-2xl bg-neon-cyan/10 border border-neon-cyan/30 shadow-[0_0_20px_rgba(34,211,238,0.25)]"
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                  />
                )}
                <Icon
                  className={`relative w-5 h-5 transition-colors ${
                    active ? "text-neon-cyan" : "text-zinc-400 group-active:text-zinc-200"
                  }`}
                  strokeWidth={active ? 2.4 : 2}
                />
                <span
                  className={`relative text-[9px] uppercase tracking-wider font-bold transition-colors ${
                    active ? "text-neon-cyan" : "text-zinc-500"
                  }`}
                >
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Shared detail modal for Search/Library */}
      <AnimatePresence>
        {openMovie && <DetailModal movie={openMovie} onClose={() => setOpenMovie(null)} />}
      </AnimatePresence>
    </div>
    </DeckProvider>
  );
}
