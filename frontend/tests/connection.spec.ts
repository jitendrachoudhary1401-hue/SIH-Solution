import {test, expect, type Page} from '@playwright/test';

test('backend unavailable on initial load shows the custom outage screen', async ({page}) => {
  await page.route('**/api/**', route => route.fulfill({status: 503, contentType: 'application/json', body: '{}'}));
  await page.goto('/officer/login');
  await expect(page.getByRole('heading', {name: 'Backend is down. Try again later.'})).toBeVisible();
  await expect(page.getByLabel('Password', {exact: true})).toHaveCount(0);
  await page.getByRole('button', {name: 'Try again', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Backend is down. Try again later.'})).toBeVisible();
  await page.unroute('**/api/**');
  await page.getByRole('button', {name: 'Try again', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Officer sign in'})).toBeVisible();
});

async function login(page: Page) {
  await page.goto('/officer/login');
  await page.getByLabel('Email address').fill('lead.rb@onecase.demo');
  await page.getByLabel('Password', {exact: true}).fill('OneCaseDemo!2026');
  await page.getByRole('button', {name: 'Sign in to workspace'}).click();
  await expect(page.getByRole('heading', {name: /Good /})).toBeVisible();
}

test('custom 404 works before and after sign-in', async ({page}) => {
  await page.goto('/a-page-that-does-not-exist');
  await expect(page.getByRole('heading', {name: 'We couldn’t find that page'})).toBeVisible();
  await page.getByRole('link', {name: 'Go to sign in'}).click();
  await login(page);
  await page.goto('/a-page-that-does-not-exist');
  await expect(page.getByRole('heading', {name: 'We couldn’t find that page'})).toBeVisible();
  await page.getByRole('link', {name: 'Return to workspace'}).click();
  await expect(page.getByRole('heading', {name: /Good /})).toBeVisible();
});

for (const failure of ['network', 'gateway'] as const) {
  test(`${failure} failure signs out, survives reload and revokes the old session on recovery`, async ({page}) => {
    await login(page);
    const oldSession = (await page.context().cookies()).find(cookie => cookie.name === 'onecase_session')!.value;
    await page.route('**/api/**', route => failure === 'network'
      ? route.abort('failed')
      : route.fulfill({status: 503, contentType: 'application/json', body: '{}'}));
    await page.getByRole('link', {name: 'Institutions', exact: true}).click();
    await expect(page).toHaveURL(/\/officer\/login$/);
    await expect(page.getByRole('heading', {name: 'Backend is down. Try again later.'})).toBeVisible();
    await expect(page.getByRole('alert')).toContainText('automatically signed out');
    await expect(page.locator('.sidebar')).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('heading', {name: 'Backend is down. Try again later.'})).toBeVisible();
    await page.getByRole('button', {name: 'Try again', exact: true}).click();
    await expect(page.getByRole('heading', {name: 'Backend is down. Try again later.'})).toBeVisible();
    await page.unroute('**/api/**');
    await page.getByRole('button', {name: 'Try again', exact: true}).click();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('onecase.logout-pending'))).toBeNull();
    const revoked = await page.request.get('/api/auth/me', {headers: {cookie: `onecase_session=${oldSession}`}});
    expect(revoked.status()).toBe(401);
    await expect(page.getByRole('heading', {name: 'Officer sign in'})).toBeVisible();
    await login(page);
  });
}

test('offline event signs out and 404 API responses do not', async ({page, context}) => {
  await login(page);
  expect((await page.request.get('/api/complaints/999999')).status()).toBe(404);
  await expect(page.locator('.sidebar')).toBeVisible();
  await context.setOffline(true);
  await expect(page.getByRole('heading', {name: 'Backend is down. Try again later.'})).toBeVisible();
  await context.setOffline(false);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('onecase.logout-pending'))).toBeNull();
  await expect(page.getByRole('heading', {name: 'Officer sign in'})).toBeVisible();
});
