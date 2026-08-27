import { expect, test } from "@playwright/test";

test.skip(
  !process.env.TEST_SUPABASE_URL || !process.env.TEST_SUPABASE_KEY,
  "TEST_SUPABASE_URL and TEST_SUPABASE_KEY are required for browser E2E",
);

test.describe("authenticated product smoke @smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/movies**", async (route) =>
      route.fulfill({ json: { ok: true, movies: [], next_cursor: null } }),
    );
    await page.route("**/api/recommendations**", async (route) =>
      route.fulfill({ json: { ok: true, movies: [], next_cursor: null } }),
    );
    await page.goto("/");
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
    await page.getByRole("button", { name: "Библиотека" }).click();
    await expect(page.getByRole("heading", { name: "БИБЛИОТЕКА" })).toBeVisible();
    await expect(page.getByText(/ФИЛЬМЫ · \d+/)).toBeVisible();
    await expect(page.getByText(/СЕРИАЛЫ · \d+/)).toBeVisible();
    await expect(page.getByText("MMT Test").first()).toBeVisible();
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
    await expect(page.getByText(/Проверяем ответ|Правильно|Неверно/)).toBeVisible();
    await page.getByRole("button", { name: "Выйти" }).click();
    await expect(page.getByRole("heading", { name: "КВИЗ" })).toBeVisible();
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
    releaseQuiz?.();
  });
});
