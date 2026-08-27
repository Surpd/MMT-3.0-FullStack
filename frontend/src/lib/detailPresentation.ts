import type { DeckMovie } from "./api";

export function hasAdditionalMovieInfo(
  movie: Pick<DeckMovie, "media_type" | "directors" | "actors" | "runtime_mins">,
): boolean {
  return Boolean(
    movie.media_type === "tv" ||
    movie.directors?.length ||
    movie.actors?.length ||
    movie.runtime_mins,
  );
}
