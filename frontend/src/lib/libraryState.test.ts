import assert from "node:assert/strict";
import test from "node:test";
import type { DeckMovie } from "@/lib/api";
import { reconcileLibraryUpdate } from "./libraryState.ts";

const series: DeckMovie = {
  movie_id: 7,
  title: "Сериал",
  poster: "",
  poster_path: "",
  media_type: "tv",
  genre_ids: [],
  genre_names: [],
  user_status: "liked",
  tv_progress: {
    watched_episodes: 0,
    available_episodes: 30,
    watched_minutes: 0,
    seasons: [],
    caught_up: false,
    completed: false,
  },
};

test("episode progress updates keep library membership and modal item", () => {
  let items = [series];
  for (const watched of [1, 2, 3]) {
    const result = reconcileLibraryUpdate(
      items,
      { ...series, tv_progress: { ...series.tv_progress!, watched_episodes: watched } },
      "liked",
    );
    items = result.items;
    assert.equal(result.updated?.user_status, "liked");
    assert.equal(result.updated?.tv_progress?.watched_episodes, watched);
    assert.equal(items.length, 1);
  }
});

test("explicit status change removes an item from the current library tab", () => {
  const result = reconcileLibraryUpdate([series], { ...series, user_status: undefined }, "liked", {
    statusChanged: true,
  });
  assert.equal(result.updated, null);
  assert.deepEqual(result.items, []);
});
