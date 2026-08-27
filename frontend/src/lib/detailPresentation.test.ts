import assert from "node:assert/strict";
import test from "node:test";
import { hasAdditionalMovieInfo } from "./detailPresentation.ts";

test("zero runtime does not render an empty movie info block", () => {
  assert.equal(
    hasAdditionalMovieInfo({
      media_type: "movie",
      directors: [],
      actors: [],
      runtime_mins: 0,
    }),
    false,
  );
});

test("real movie info still renders the details block", () => {
  assert.equal(
    hasAdditionalMovieInfo({
      media_type: "movie",
      directors: ["Director"],
      actors: [],
      runtime_mins: 0,
    }),
    true,
  );
});
