import assert from "node:assert/strict";
import test from "node:test";
import { applyOptimisticProgress } from "./tvProgress.ts";

const baseProgress = {
  seasons: [
    {
      season_number: 1,
      episode_count: 3,
      available_episode_count: 3,
      watched_episode_count: 0,
      episodes: [
        { season_number: 1, episode_number: 1, air_date: "2020-01-01", watched: false },
        { season_number: 1, episode_number: 2, air_date: "2020-01-02", watched: false },
        { season_number: 1, episode_number: 3, air_date: "2020-01-03", watched: false },
      ],
    },
  ],
  watched_episodes: 0,
  available_episodes: 3,
  caught_up: false,
  completed: false,
  state: "none" as const,
};

test("keeps cumulative optimistic state across multiple episode updates", () => {
  const first = applyOptimisticProgress(baseProgress, {
    season_number: 1,
    episode_number: 1,
    watched: true,
  });
  const second = applyOptimisticProgress(first, {
    season_number: 1,
    episode_number: 2,
    watched: true,
  });
  const third = applyOptimisticProgress(second, {
    season_number: 1,
    episode_number: 3,
    watched: true,
  });

  assert.deepEqual(
    third.seasons[0].episodes.map((episode) => episode.watched),
    [true, true, true],
  );
  assert.equal(third.watched_episodes, 3);
  assert.equal(third.caught_up, true);
});
