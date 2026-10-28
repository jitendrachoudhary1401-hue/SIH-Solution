import { expect, test } from './fixtures';

test('case-coordination logo stays square on desktop and phone', async ({ page }) => {
  for (const [width, height, name] of [[1440, 1000, 'desktop'], [390, 844, 'phone']] as const) {
    await page.setViewportSize({ width, height });
    await page.goto('/officer/login');
    const logo = page.getByRole('img', { name: 'OneCase', exact: true });
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute('src', '/onecase-emblem.png');
    const dimensions = await logo.evaluate((image: HTMLImageElement) => ({ width: image.naturalWidth, height: image.naturalHeight }));
    expect(dimensions.width).toBeGreaterThan(0);
    expect(dimensions.width).toBe(dimensions.height);
    const box = await logo.boundingBox();
    expect(box!.width).toBe(box!.height);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `../output/review/onecase-login-${name}.png`, fullPage: true });
  }
});
