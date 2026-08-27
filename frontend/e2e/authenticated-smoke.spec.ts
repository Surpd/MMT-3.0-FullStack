import { expect, test } from "@playwright/test";

const hasReservedUserOptIn = process.env.ALLOW_PRODUCTION_TEST_USER === "true";
test.skip(
  !hasReservedUserOptIn,
  "Set ALLOW_PRODUCTION_TEST_USER=true for the reserved synthetic user",
);

test.describe("authenticated product smoke @smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/movies**", async (route) =>
      route.fulfill({ json: { ok: true, movies: [], next_cursor: null } }),
    );
    await page.route("**/api/recommendations**", async (route) =>
      route.fulfill({ json: { ok: true, movies: [], next_cursor: null } }),
    );
    const initialTasteResponse = page.waitForResponse(
      (response) => response.url().includes("/api/profile/taste") && response.status() === 200,
    );
    await page.goto("/");
    await initialTasteResponse;
  });

  test("boots as the test user and renders navigation", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Профиль" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Библиотека" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Квиз" })).toBeVisible();
    await expect(page.getByText("Telegram user identity is unavailable")).toHaveCount(0);
  });

  test("loads Profile without an endless loader", async ({ page }) => {
    await page.getByRole("button", { name: "Профиль" }).click();
    await expect(page.getByRole("heading", { name: "ПРОФИЛЬ" })).toBeVisible();
    await expect(page.getByText("Загрузка…")).toHaveCount(0);
    await expect(page.getByText("ФИЛЬМЫ")).toBeVisible();
  });

  test("loads the deterministic movie and TV library", async ({ page }) => {
    const libraryResponse = page.waitForResponse(
      (response) => response.url().includes("/api/library") && response.status() === 200,
    );
    await page.getByRole("button", { name: "Библиотека" }).click();
    await expect(page.getByRole("heading", { name: "БИБЛИОТЕКА" })).toBeVisible();
    await expect(page.getByText(/ФИЛЬМЫ · \d+/)).toBeVisible();
    await expect(page.getByText(/СЕРИАЛЫ · \d+/)).toBeVisible();
    const payload = (await (await libraryResponse).json()) as {
      movies?: Array<{ title?: string; media_type?: string }>;
    };
    expect(payload.movies?.length).toBeGreaterThan(0);
    expect(new Set(payload.movies?.map((movie) => movie.media_type)).size).toBeGreaterThan(1);
    const firstTitle = payload.movies?.[0]?.title;
    expect(firstTitle).toBeTruthy();
    await expect(page.getByText(firstTitle!, { exact: true }).first()).toBeVisible();
  });

  test("starts My Library Quiz, accepts an answer and returns home", async ({ page }) => {
    await page.getByRole("button", { name: "Квиз" }).click();
    await expect(page.getByRole("heading", { name: "КВИЗ" })).toBeVisible();
    const libraryMode = page.getByRole("button", { name: /Моя библиотека/ });
    await expect(libraryMode).toBeEnabled();
    await libraryMode.click();
    await expect(page.getByText(/1 \/ 10/)).toBeVisible();
    const answer = page.locator("button:has(span.rounded-full)").first();
    await expect(answer).toBeEnabled();
    await answer.click();
    await expect(page.getByText(/Верно|Неверно/)).toBeVisible();
    await page.getByRole("button", { name: "Выйти" }).click();
    await expect(page.getByRole("heading", { name: "КВИЗ" })).toBeVisible();
  });

  test("plays Quiz locally and completes exactly once", async ({ page }) => {
    const answerRequests: string[] = [];
    let sessionRequests = 0;
    let completionRequests = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/quiz/answer")) answerRequests.push(request.url());
      if (request.url().includes("/api/quiz?mode=library")) sessionRequests += 1;
      if (request.url().includes("/api/quiz/complete")) completionRequests += 1;
    });

    await page.getByRole("button", { name: "Квиз" }).click();
    await page.getByRole("button", { name: /Моя библиотека/ }).click();
    await expect(page.getByText(/1 \/ 10/)).toBeVisible();
    for (let index = 0; index < 10; index += 1) {
      await page.locator("button:has(span.rounded-full)").first().click();
      if (index < 9) await expect(page.getByText(new RegExp(`${index + 2} / 10`))).toBeVisible();
    }
    await expect(page.getByText("СЕССИЯ ЗАВЕРШЕНА")).toBeVisible();
    expect(sessionRequests).toBe(1);
    expect(answerRequests).toHaveLength(0);
    expect(completionRequests).toBe(1);
  });

  test("navigation remains responsive while a Quiz request is pending", async ({ page }) => {
    let releaseQuiz: (() => void) | undefined;
    const quizResponse = new Promise<void>((resolve) => {
      releaseQuiz = resolve;
    });
    await page.route("**/api/quiz*", async (route) => {
      if (new URL(route.request().url()).searchParams.get("mode") !== "library") {
        await route.continue();
        return;
      }
      await quizResponse;
      await route.continue();
    });
    await page.getByRole("button", { name: "Квиз" }).click();
    await expect(page.getByRole("heading", { name: "КВИЗ" })).toBeVisible();
    await page.getByRole("button", { name: /Моя библиотека/ }).click();
    await page.getByRole("button", { name: "Профиль" }).click();
    await expect(page.getByRole("heading", { name: "ПРОФИЛЬ" })).toBeVisible();
    await page.getByRole("button", { name: "Библиотека" }).click();
    await expect(page.getByRole("heading", { name: "БИБЛИОТЕКА" })).toBeVisible();
    releaseQuiz?.();
    await page.waitForTimeout(100);
    await expect(page.getByRole("heading", { name: "БИБЛИОТЕКА" })).toBeVisible();
    await expect(page.getByText(/1 \/ 10/)).toHaveCount(0);
  });
});
