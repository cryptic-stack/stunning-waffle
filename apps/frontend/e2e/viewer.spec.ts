import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000";
const authHeaders = process.env.PLAYWRIGHT_AUTH_USER_ID
  ? {
      "X-User-Id": process.env.PLAYWRIGHT_AUTH_USER_ID,
      ...(process.env.PLAYWRIGHT_AUTH_USER_EMAIL
        ? { "X-User-Email": process.env.PLAYWRIGHT_AUTH_USER_EMAIL }
        : {}),
      ...(process.env.PLAYWRIGHT_AUTH_USER_NAME
        ? { "X-User-Name": process.env.PLAYWRIGHT_AUTH_USER_NAME }
        : {}),
    }
  : undefined;

async function cleanupSessions(request: APIRequestContext) {
  const response = await request.get(`${apiBaseUrl}/api/v1/sessions`, {
    headers: authHeaders,
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { items: Array<{ session_id: string }> };
  for (const session of payload.items) {
    const deleteResponse = await request.delete(`${apiBaseUrl}/api/v1/sessions/${session.session_id}`, {
      headers: authHeaders,
    });
    expect(deleteResponse.ok()).toBeTruthy();
  }
}

async function expectViewerTrack(page: Page) {
  await expect
    .poll(
      () =>
        page.getByLabel("Remote session video").evaluate((node) => {
          const video = node as HTMLVideoElement;
          const stream = video.srcObject as MediaStream | null;
          return stream ? stream.getTracks().length : 0;
        }),
      { timeout: 45_000 },
    )
    .toBeGreaterThan(0);
}

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ request }) => {
  await cleanupSessions(request);
});

test.afterEach(async ({ request }) => {
  await cleanupSessions(request);
});

test("launches a browser session through the real UI and attaches media", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Browserlab" })).toBeVisible();

  await page.getByLabel("Target URL").fill("https://example.com");
  await page.getByRole("button", { name: "Launch Session" }).click();

  await expect.poll(() => page.locator(".session-item").count()).toBe(1);
  const sessionItem = page.locator(".session-item").first();
  await expect(sessionItem).toContainText("Chrome");
  await expectViewerTrack(page);

  await sessionItem.getByRole("button", { name: "End" }).click();
  await expect.poll(() => page.locator(".session-item").count()).toBe(0);
});

test("switches to desktop mode and launches a Kali desktop session", async ({ page }) => {
  await page.goto("/");

  await page.locator('[aria-label="Session modes"]').getByRole("button", { name: "Desktop" }).click();
  await expect(page.getByLabel("Target URL")).toHaveCount(0);

  await page.locator('[aria-label="Runtime choices"] .browser-card').filter({ hasText: "Kali XFCE" }).click();
  await page.getByRole("button", { name: "Launch Session" }).click();

  await expect.poll(() => page.locator(".session-item").count()).toBe(1);
  const sessionItem = page.locator(".session-item").first();
  await expect(sessionItem).toContainText("Kali XFCE");
  await expect(sessionItem).toContainText("Full desktop session");
  await expectViewerTrack(page);

  await sessionItem.getByRole("button", { name: "End" }).click();
  await expect.poll(() => page.locator(".session-item").count()).toBe(0);
});
