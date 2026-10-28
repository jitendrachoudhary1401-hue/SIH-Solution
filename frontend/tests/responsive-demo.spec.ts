import {test, expect} from '@playwright/test';

for (const width of [320, 390, 768, 820, 1024]) {
  test(`login and demo workspace fit a ${width}px viewport`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    await page.goto('/officer/login');
    await expect(page.getByRole('heading', {name: 'Sign in to OneCase'})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await expect(page.locator('.login-story')).not.toBeVisible();
    expect(await page.getByLabel('Email address').evaluate(el => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
    await page.screenshot({path: `test-results/login-${width}.png`, fullPage: true});
    await page.getByRole('button', {name: 'Demo accounts', exact: true}).click();
    const dialog = page.getByRole('region', {name: 'Demo account options'});
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('.demo-role')).toHaveCount(13);
    await expect(dialog.getByRole('button', {name: 'Try Admin demo'})).toHaveCount(0);
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await page.screenshot({path: `test-results/demo-chooser-${width}.png`, fullPage: true});
    await dialog.getByRole('button', {name: 'Try Lead demo', exact: true}).click();
    await expect(page.getByRole('heading', {name: /Good /})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await expect(page.locator('.sidebar')).not.toBeVisible();
    await page.getByRole('button', {name: 'Open navigation'}).click();
    await expect(page.getByRole('dialog', {name: 'Workspace navigation'})).toBeVisible();
    await page.getByRole('link', {name: 'Complaints', exact: true}).click();
    await expect(page.getByRole('dialog', {name: 'Workspace navigation'})).not.toBeVisible();
    await expect(page.getByRole('heading', {name: 'Complaints', exact: true})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({path: `test-results/workspace-${width}.png`, fullPage: true});
  });
}

test('registration and recovery fit phone and tablet widths', async ({page}) => {
  for (const width of [320, 390, 768, 1024]) {
    await page.setViewportSize({width, height: 900});
    for (const path of ['/register/student-parent', '/register/other', '/forgot-password', '/reset-password']) {
      await page.goto(path);
      await expect(page.locator('h1')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    }
  }
});

test('every demo role can sign in directly from the login page', async ({page}) => {
  const roles = ['Student', 'Parent', 'Faculty', 'Staff', 'Other', 'Faculty Reviewer', 'Officer', 'Lead', 'Reviewer', 'Committee', 'Verifier', 'Executive', 'Auditor'];
  for (const role of roles) {
    await page.context().clearCookies();
    await page.goto('/officer/login');
    await page.getByRole('button', {name: 'Demo accounts', exact: true}).click();
    await page.getByRole('button', {name: `Try ${role} demo`, exact: true}).click();
    await expect(page.locator('.main-content h1')).toBeVisible();
    const identity = await (await page.request.get('/api/auth/me')).json();
    expect(identity.user.role).toBe(role.toLowerCase().replaceAll(' ', '_'));
    expect(identity.user.is_demo).toBe(true);
  }
});
