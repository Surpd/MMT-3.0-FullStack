import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE } from './api';

export interface Movie {
  id: number;
  title: string;
  poster_path?: string;
  overview: string;
  vote_average: number;
  release_date: string;
}

interface DeckContextType {
  deck: Movie[];
  currentMovie: Movie | null;
  popMovie: () => void;
  loading: boolean;
  setDeck: React.Dispatch<React.SetStateAction<Movie[]>>; // <-- ДОБАВИЛИ ЭТО
}

const DeckContext = createContext<DeckContextType | undefined>(undefined);

export const DeckProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [deck, setDeck] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<number>>(new Set());

  // ПРЕДОХРАНИТЕЛЬ: чтобы не было бесконечных циклов
  const isFetching = useRef(false);
  const cursorRef = useRef(0);

  const fetchMovies = useCallback(async () => {
    // Если уже грузим - выходим
    if (isFetching.current) return;
    
    isFetching.current = true;
    setLoading(true);
    
    try {
      // Пытаемся достать ID юзера из Телеграма. Если мы в браузере на компе - берем 123456
      const tg = (window as any).Telegram?.WebApp;
      const userId = tg?.initDataUnsafe?.user?.id || 429426063;

      // ТЕПЕРЬ ОТПРАВЛЯЕМ ЗАПРОС ПРАВИЛЬНО: с указанием user_id
      const response = await fetch(`${API_BASE}/api/movies?user_id=${userId}&cursor=${cursorRef.current}`);
      
      // Если сервер вернул 400 или 500 - выходим без паники
      if (!response.ok) {
        console.error("Сервер вернул ошибку:", response.status);
        return;
      }

      const data = await response.json();
      
      if (data.ok && data.movies) {
        // ????????? ?????? ??? ?????????? ???????
        if (typeof data.next_cursor === 'number') {
          cursorRef.current = data.next_cursor;
        } else {
          cursorRef.current = 0;
        }

        // 1. ???????? ID ? ??????? ????????? (?????? ?????? ?????? movie_id)
        const normalizedMovies = data.movies.map((m: any) => ({
          ...m,
          id: m.movie_id || m.id,
        }));

        // 2. ????????? ?????????
        const newMovies = normalizedMovies.filter(
          (m: any) => !seenIds.has(m.id) && !deck.some(d => d.id === m.id)
        );

        if (newMovies.length > 0) {
          // 3. ????? ???????? TMDB (??? ? ??????????)
          const moviesWithImages = newMovies.map((m: any) => {
            const rawPoster = m.poster_url || m.poster_path || "";
            const finalPoster = rawPoster.startsWith("http")
              ? rawPoster
              : (rawPoster ? `https://image.tmdb.org/t/p/w500${rawPoster}` : undefined);

            return {
              ...m,
              poster_path: finalPoster,
              poster: finalPoster // ????????? ??? ?????????? UI
            };
          });

          setDeck(prev => [...prev, ...moviesWithImages]);
          setSeenIds(prev => {
            const next = new Set(prev);
            newMovies.forEach((m: any) => next.add(m.id));
            return next;
          });
        }
      }
    } catch (error) {
      console.error("Ошибка сети или сервера:", error);
    } finally {
      // Снимаем блокировки
      setLoading(false);
      isFetching.current = false;
    }
  }, [seenIds, deck]);

  // Запуск при пустой колоде (убрали fetchMovies из зависимостей, чтобы убить цикл)
  useEffect(() => {
    if (deck.length === 0) {
      fetchMovies();
    }
  }, [deck.length]);

  // Подгрузка, когда остался 1 фильм
  useEffect(() => {
    if (deck.length === 1) {
      fetchMovies();
    }
  }, [deck.length]);

  const popMovie = useCallback(() => {
    setDeck(prev => prev.slice(1));
  }, []);

  const currentMovie = deck.length > 0 ? deck[0] : null;

  return (
    <DeckContext.Provider value={{ deck, currentMovie, popMovie, loading, setDeck }}>
      {children}
    </DeckContext.Provider>
  );
};

export const useDeck = () => {
  const context = useContext(DeckContext);
  if (context === undefined) {
    throw new Error('useDeck must be used within a DeckProvider');
  }
  return context;
};





