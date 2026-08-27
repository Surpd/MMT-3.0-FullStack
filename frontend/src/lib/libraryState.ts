import type { DeckMovie, LibraryStatus } from "@/lib/api";

export type LibraryUpdate = { statusChanged?: boolean };

export function libraryMovieKey(movie: Pick<DeckMovie, "movie_id" | "media_type">): string {
  return `${movie.media_type}:${movie.movie_id}`;
}

export function reconcileLibraryUpdate(
  items: DeckMovie[],
  updated: DeckMovie,
  activeTab: LibraryStatus,
  options: LibraryUpdate = {},
): { items: DeckMovie[]; updated: DeckMovie | null } {
  const key = libraryMovieKey(updated);
  const existing = items.find((item) => libraryMovieKey(item) === key);
  const nextStatus = options.statusChanged
    ? updated.user_status
    : (updated.user_status ?? existing?.user_status);
  const merged = { ...existing, ...updated, user_status: nextStatus } as DeckMovie;
  const shouldRemove = Boolean(options.statusChanged && nextStatus !== activeTab);

  return {
    items: shouldRemove
      ? items.filter((item) => libraryMovieKey(item) !== key)
      : items.map((item) => (libraryMovieKey(item) === key ? merged : item)),
    updated: shouldRemove ? null : merged,
  };
}
