import type { TvProgress } from "./api";

export function applyOptimisticProgress(
  progress: TvProgress,
  body: { season_number: number; episode_number?: number; watched: boolean },
): TvProgress {
  const seasons = progress.seasons.map((season) => {
    if (season.season_number !== body.season_number) return season;
    const episodes = season.episodes.map((episode) =>
      body.episode_number == null || episode.episode_number !== body.episode_number
        ? episode
        : { ...episode, watched: body.watched },
    );
    const aired = episodes.filter(
      (episode) => episode.air_date && new Date(`${episode.air_date}T23:59:59`) <= new Date(),
    );
    const watched =
      body.episode_number == null
        ? body.watched
          ? aired.length
          : 0
        : aired.filter((episode) => episode.watched).length;
    return { ...season, episodes, watched_episode_count: watched };
  });
  const available = seasons.reduce((sum, season) => sum + (season.available_episode_count ?? 0), 0);
  const watched = seasons.reduce((sum, season) => sum + season.watched_episode_count, 0);
  const availableEpisodes = available || progress.available_episodes;
  const nextEpisode = seasons
    .flatMap((season) => season.episodes)
    .filter((episode) => episode.air_date && new Date(`${episode.air_date}T23:59:59`) <= new Date())
    .filter((episode) => !episode.watched)
    .sort(
      (a, b) =>
        (a.season_number ?? 0) - (b.season_number ?? 0) || a.episode_number - b.episode_number,
    )[0];
  return {
    ...progress,
    seasons,
    available_episodes: availableEpisodes,
    watched_episodes: watched,
    next_episode: nextEpisode ?? (watched === availableEpisodes ? null : progress.next_episode),
    caught_up: availableEpisodes > 0 && watched === availableEpisodes,
    completed: progress.completed && availableEpisodes > 0 && watched === availableEpisodes,
    state:
      availableEpisodes > 0 && watched === availableEpisodes
        ? "caught_up"
        : watched > 0
          ? "watching"
          : progress.state,
  };
}
