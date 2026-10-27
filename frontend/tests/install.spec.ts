import { expect, test } from '@playwright/test';

test('installation metadata and help are available before sign-in', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/officer/login');
  const manifestUrl = await page.locator('link[rel="manifest"]').getAttribute('href');
  const response = await page.request.get(manifestUrl!);
  expect(response.headers()['content-type']).toContain('json');
  const manifest = await response.json();
  expect(manifest.display).toBe('standalone');
  for (const icon of manifest.icons) {
    const dimensions = await page.evaluate(async (src: string) => {
      const image = new Image();
      image.src = src;
      await image.decode();
      return `${image.naturalWidth}x${image.naturalHeight}`;
    }, icon.src);
    expect(dimensions).toBe(icon.sizes);
  }
  await page.getByRole('button', { name: 'Install OneCase', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Add to Home Screen');
  await expect(page.getByRole('dialog')).toContainText('internet connection');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../tmp/onecase-install-mobile.png' });
});

test('install control uses the browser prompt and hides after acceptance', async ({ page }) => {
  await page.goto('/officer/login');
  await expect(page.getByRole('button', { name: 'Install OneCase', exact: true })).toBeVisible();
  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    Object.assign(event, {
      prompt: async () => { document.documentElement.dataset.installPrompted = 'true'; },
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    });
    window.dispatchEvent(event);
  });
  await page.getByRole('button', { name: 'Install OneCase', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-install-prompted', 'true');
  await expect(page.getByRole('button', { name: 'Install OneCase', exact: true })).toHaveCount(0);
});

test('standalone app windows hide the install control', async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.matchMedia.bind(window);
    window.matchMedia = (query: string) => query === '(display-mode: standalone)'
      ? Object.defineProperty(original(query), 'matches', { value: true }) : original(query);
  });
  await page.goto('/officer/login');
  await expect(page.getByRole('heading', { name: 'Sign in to OneCase' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Install OneCase', exact: true })).toHaveCount(0);
});
