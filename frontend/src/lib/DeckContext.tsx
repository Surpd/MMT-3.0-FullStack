import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { fetchMovies, type DeckMovie } from "./api";

type DeckContextValue = {
  deck: DeckMovie[];
  setDeck: React.Dispatch<React.SetStateAction<DeckMovie[]>>;
  cursor: number;
  hasMore: boolean;
  loading: boolean;
  loadMore: () => void;
};

const DeckContext = createContext<DeckContextValue | null>(null);

export function DeckProvider({ children }: { children: ReactNode }) {
  const [deck, setDeck] = useState<DeckMovie[]>([]);
  const [cursor, setCursor] = useState<number>(0);
  const cursorRef = useRef<number>(0);
  const hasMoreRef = useRef<boolean>(true);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [loading, setLoading] = useState(true);
  const fetchingRef = useRef(false);
  const initRef = useRef(false);

  const loadMore = async () => {
    if (fetchingRef.current || !hasMoreRef.current) return;
    fetchingRef.current = true;
    try {
      const fromCursor = cursorRef.current;
      const { movies, next_cursor } = await fetchMovies(fromCursor);
      setDeck((d) => [...d, ...movies]);
      if (next_cursor === null || next_cursor === fromCursor) {
        hasMoreRef.current = false;
        setHasMore(false);
      } else {
        cursorRef.current = next_cursor;
        setCursor(next_cursor);
        if (movies.length === 0) {
          hasMoreRef.current = false;
          setHasMore(false);
        }
      }
    } catch (e) {
      console.warn("[movies] failed", e);
      hasMoreRef.current = false;
      setHasMore(false);
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  };

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <DeckContext.Provider value={{ deck, setDeck, cursor, hasMore, loading, loadMore }}>
      {children}
    </DeckContext.Provider>
  );
}

export function useDeck() {
  const ctx = useContext(DeckContext);
  if (!ctx) throw new Error("useDeck must be used inside DeckProvider");
  return ctx;
}
