import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { fetchRecommendations, getUserId, type DeckMovie, type RecommendationParams } from "./api";

export const DISCOVER_SETTINGS_KEY = "discover_filters";

export type DiscoverSettings = {
  targetType: "mix" | "movie" | "tv";
  minYear: number;
  maxYear: number;
  minRating: number;
};

export const DEFAULT_DISCOVER_SETTINGS: DiscoverSettings = {
  targetType: "mix",
  minYear: 1950,
  maxYear: new Date().getFullYear(),
  minRating: 5.0,
};

export function loadDiscoverSettings(): DiscoverSettings {
  try {
    const raw = localStorage.getItem(DISCOVER_SETTINGS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<DiscoverSettings>;
      const storedMin =
        typeof parsed.minYear === "number" ? parsed.minYear : DEFAULT_DISCOVER_SETTINGS.minYear;
      const storedMax =
        typeof parsed.maxYear === "number" ? parsed.maxYear : DEFAULT_DISCOVER_SETTINGS.maxYear;
      return {
        targetType: parsed.targetType ?? DEFAULT_DISCOVER_SETTINGS.targetType,
        minYear: Math.min(storedMin, storedMax),
        maxYear: Math.max(storedMin, storedMax),
        minRating:
          typeof parsed.minRating === "number"
            ? parsed.minRating
            : DEFAULT_DISCOVER_SETTINGS.minRating,
      };
    }
  } catch {
    // ignore
  }
  return DEFAULT_DISCOVER_SETTINGS;
}

export function saveDiscoverSettings(settings: DiscoverSettings): void {
  localStorage.setItem(DISCOVER_SETTINGS_KEY, JSON.stringify(settings));
}

export function settingsToParams(settings: DiscoverSettings): RecommendationParams {
  return {
    target_type: settings.targetType,
    min_year: settings.minYear,
    max_year: settings.maxYear,
    min_rating: settings.minRating,
  };
}

interface DeckContextType {
  deck: DeckMovie[];
  setDeck: React.Dispatch<React.SetStateAction<DeckMovie[]>>;
  loading: boolean;
  hasMore: boolean;
  loadMore: () => void;
  applyFilters: (settings: DiscoverSettings) => void;
}

const DeckContext = createContext<DeckContextType | undefined>(undefined);

export const DeckProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [deck, setDeck] = useState<DeckMovie[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const isFetching = useRef(false);
  const pendingReset = useRef(false);
  const skipRef = useRef(0);
  const filtersRef = useRef<RecommendationParams>(settingsToParams(loadDiscoverSettings()));

  const fetchBatch = useCallback(async (reset: boolean) => {
    if (isFetching.current) {
      if (reset) pendingReset.current = true;
      return;
    }

    isFetching.current = true;
    setLoading(true);

    try {
      const skip = reset ? 0 : skipRef.current;
      const result = await fetchRecommendations(getUserId(), skip, filtersRef.current);

      if (typeof result.next_cursor === "number") {
        skipRef.current = result.next_cursor;
      } else if (result.movies.length > 0) {
        skipRef.current = skip + result.movies.length;
      }

      setHasMore(result.movies.length > 0);

      if (result.movies.length > 0) {
        setDeck((prev) => (reset ? result.movies : [...prev, ...result.movies]));
      } else if (reset) {
        setDeck([]);
      }
    } catch (error) {
      console.error("Ошибка загрузки рекомендаций:", error);
      setHasMore(false);
    } finally {
      setLoading(false);
      isFetching.current = false;
      if (pendingReset.current) {
        pendingReset.current = false;
        void fetchBatch(true);
      }
    }
  }, []);

  const loadMore = useCallback(() => {
    void fetchBatch(false);
  }, [fetchBatch]);

  const applyFilters = useCallback(
    (settings: DiscoverSettings) => {
      saveDiscoverSettings(settings);
      filtersRef.current = settingsToParams(settings);
      skipRef.current = 0;
      setHasMore(true);
      setDeck([]);
      void fetchBatch(true);
    },
    [fetchBatch],
  );

  useEffect(() => {
    void fetchBatch(true);
  }, [fetchBatch]);

  useEffect(() => {
    const handleTasteUpdate = () => {
      // Keep visible cards stable; the next prefetch starts from the new
      // profile-versioned pool and session exclusion prevents duplicates.
      skipRef.current = 0;
      setHasMore(true);
      if (deck.length === 0 && !isFetching.current) void fetchBatch(true);
    };
    window.addEventListener("mmt:taste-updated", handleTasteUpdate);
    return () => window.removeEventListener("mmt:taste-updated", handleTasteUpdate);
  }, [deck.length, fetchBatch]);

  return (
    <DeckContext.Provider value={{ deck, setDeck, loading, hasMore, loadMore, applyFilters }}>
      {children}
    </DeckContext.Provider>
  );
};

export const useDeck = () => {
  const context = useContext(DeckContext);
  if (context === undefined) {
    throw new Error("useDeck must be used within a DeckProvider");
  }
  return context;
};
