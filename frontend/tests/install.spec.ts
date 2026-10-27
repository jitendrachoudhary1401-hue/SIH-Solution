import { expect, test } from '@playwright/test';

test('native installation metadata is available before sign-in', async ({ page }) => {
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
  await expect(page.getByRole('heading', { name: 'Sign in to OneCase' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Install OneCase', exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('direct install opens the browser prompt without an instructions dialog', async ({ page }) => {
  await page.goto('/officer/login');
  await expect(page.getByRole('heading', { name: 'Sign in to OneCase' })).toBeVisible();
  const cancelled = await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    Object.assign(event, {
      prompt: async () => { document.documentElement.dataset.installPrompted = 'true'; },
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  expect(cancelled).toBe(false);
  await page.getByRole('button', { name: 'Install OneCase', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-install-prompted', 'true');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Install OneCase', exact: true })).toHaveCount(0);
});

test('dismissing native installation consumes the offer without opening help', async ({ page }) => {
  await page.goto('/officer/login');
  await expect(page.getByRole('heading', { name: 'Sign in to OneCase' })).toBeVisible();
  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    Object.assign(event, { prompt: async () => {}, userChoice: Promise.resolve({ outcome: 'dismissed' }) });
    window.dispatchEvent(event);
  });
  await page.getByRole('button', { name: 'Install OneCase', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Install OneCase', exact: true })).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
