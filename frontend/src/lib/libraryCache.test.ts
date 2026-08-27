import assert from "node:assert/strict";
import test from "node:test";
import { fetchLibrary, getCachedLibrary, patchLibraryCache, type ApiMovie } from "./api.ts";

const originalFetch = globalThis.fetch;

function setTelegramUser(id: number) {
  globalThis.window = {
    Telegram: { WebApp: { initDataUnsafe: { user: { id } }, initData: "test" } },
  } as unknown as Window & typeof globalThis;
}

function response(movies: ApiMovie[], total: number): Response {
  return { ok: true, json: async () => ({ ok: true, movies, total }) } as Response;
}

test.afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("library emits page one before completing sequential background pagination", async () => {
  setTelegramUser(4101);
  const requestedPages: number[] = [];
  const updates: Array<{ count: number; complete: boolean }> = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const page = Number(new URL(String(input)).searchParams.get("page"));
    requestedPages.push(page);
    const movie = (id: number): ApiMovie => ({
      movie_id: id,
      title: `Movie ${id}`,
      media_type: "movie",
      poster_path: `/poster-${id}.jpg`,
    });
    return page === 1 ? response([movie(1)], 2) : response([movie(2)], 2);
  }) as typeof fetch;

  const result = await fetchLibrary("liked", 1, {
    onUpdate: (items, _total, complete) => updates.push({ count: items.length, complete }),
  });

  assert.deepEqual(requestedPages, [1, 2]);
  assert.deepEqual(updates[0], { count: 1, complete: false });
  assert.deepEqual(updates.at(-1), { count: 2, complete: true });
  assert.equal(result.length, 2);
  assert.equal(getCachedLibrary("liked")?.length, 2);

  globalThis.fetch = (async () => {
    throw new Error("fresh session cache should satisfy the request");
  }) as typeof fetch;
  const cachedUpdates: Array<{ count: number; complete: boolean }> = [];
  const cachedResult = await fetchLibrary("liked", 1, {
    onUpdate: (items, _total, complete) => cachedUpdates.push({ count: items.length, complete }),
  });
  assert.equal(cachedResult.length, 2);
  assert.deepEqual(cachedUpdates, [{ count: 2, complete: true }]);
  assert.deepEqual(requestedPages, [1, 2]);
});

test("library cache patches an existing snapshot without a refetch", async () => {
  setTelegramUser(4102);
  globalThis.fetch = (async () =>
    response(
      [
        {
          movie_id: 20,
          title: "Cached",
          media_type: "movie",
          poster_path: "/poster.jpg",
        },
      ],
      1,
    )) as typeof fetch;

  await fetchLibrary("liked");
  const cached = getCachedLibrary("liked");
  assert.ok(cached);
  patchLibraryCache({ ...cached[0], user_rating: 5 });
  assert.equal(getCachedLibrary("liked")?.[0].user_rating, 5);
});

test("dashboard can keep only page one until the full list is requested", async () => {
  setTelegramUser(4103);
  const requestedPages: number[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const page = Number(new URL(String(input)).searchParams.get("page"));
    requestedPages.push(page);
    const movie: ApiMovie = {
      movie_id: page,
      title: `Movie ${page}`,
      media_type: "movie",
      poster_path: "/poster.jpg",
    };
    return response([movie], 2);
  }) as typeof fetch;

  const firstPage = await fetchLibrary("watchlist", 1, { loadAll: false });
  assert.equal(firstPage.length, 1);
  assert.deepEqual(requestedPages, [1]);

  const fullList = await fetchLibrary("watchlist", 1, { loadAll: true });
  assert.equal(fullList.length, 2);
  assert.deepEqual(requestedPages, [1, 2]);
});
