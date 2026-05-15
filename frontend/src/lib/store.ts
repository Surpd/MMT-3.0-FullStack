import { useSyncExternalStore } from "react";

export type LibraryStatus = "watched" | "wishlist" | "archive";

type State = {
  status: Record<string, LibraryStatus>; // movieId -> status
  quizHighScore: number;
};

let state: State = {
  status: {},
  quizHighScore: 0,
};

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

export const store = {
  getSnapshot(): State {
    return state;
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  setStatus(movieId: string, status: LibraryStatus) {
    state = { ...state, status: { ...state.status, [movieId]: status } };
    emit();
  },
  removeStatus(movieId: string) {
    const next = { ...state.status };
    delete next[movieId];
    state = { ...state, status: next };
    emit();
  },
  setQuizScore(score: number) {
    if (score > state.quizHighScore) {
      state = { ...state, quizHighScore: score };
      emit();
    }
  },
};

export function useStore<T>(selector: (s: State) => T): T {
  return useSyncExternalStore(
    store.subscribe,
    () => selector(store.getSnapshot()),
    () => selector(store.getSnapshot())
  );
}
