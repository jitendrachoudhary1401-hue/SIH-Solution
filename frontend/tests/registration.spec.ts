import { test, expect, type Page } from '@playwright/test';

async function fillRegistration(page: Page, email: string) {
  await page.getByLabel('Full name', {exact: true}).fill('Registration Browser User');
  await page.getByLabel('Email address', {exact: true}).fill(email);
  await page.getByLabel('Password', {exact: true}).fill('PersonalPassphrase!2026');
  await page.getByLabel('Confirm password', {exact: true}).fill('PersonalPassphrase!2026');
}

test('student and parent registration saves real accounts with empty workspaces', async ({ page }) => {
  for (const kind of ['student', 'parent']) {
    const email = `browser-${kind}@example.com`;
    await page.goto('/officer/login');
    await page.getByRole('link', {name: 'Register as a student or parent'}).click();
    await expect(page.getByRole('heading', {name: 'Student & parent registration'})).toBeVisible();
    await page.getByLabel('Account type').selectOption(kind);
    await fillRegistration(page, email);
    await page.getByRole('button', {name: 'Create account', exact: true}).click();
    await expect(page.getByRole('heading', {name: 'Account created', exact: true})).toBeVisible();
    await page.getByRole('link', {name: 'Continue to sign in'}).click();
    await page.getByLabel('Email address', {exact: true}).fill(email);
    await page.getByLabel('Password', {exact: true}).fill('PersonalPassphrase!2026');
    await page.getByRole('button', {name: 'Sign in to workspace'}).click();
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByRole('heading', {name: 'A fresh start'})).toBeVisible();
    await expect(page.locator('.stat-card>strong')).toHaveText(['0', '0', '0', '0']);
    await page.reload();
    await expect(page.locator('.stat-card>strong')).toHaveText(['0', '0', '0', '0']);
    await page.getByRole('button', {name: 'Sign out', exact: true}).click();
    await expect(page.getByRole('heading', {name: 'Sign in to OneCase'})).toBeVisible();
  }
});

test('staff registration persists an access request without staff privileges', async ({ page }) => {
  await page.goto('/register/other');
  await page.getByLabel('Account type').selectOption('admin');
  await fillRegistration(page, 'browser-admin-request@example.com');
  await page.getByLabel('Organization', {exact: true}).fill('Example institution');
  await page.getByRole('button', {name: 'Create account', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Account created', exact: true})).toBeVisible();
  await page.getByRole('link', {name: 'Continue to sign in'}).click();
  await page.getByLabel('Email address', {exact: true}).fill('browser-admin-request@example.com');
  await page.getByLabel('Password', {exact: true}).fill('PersonalPassphrase!2026');
  await page.getByRole('button', {name: 'Sign in to workspace'}).click();
  await expect(page.getByText('Access request awaiting approval', {exact: true})).toBeVisible();
  await expect(page.locator('.stat-card>strong')).toHaveText(['0', '0', '0', '0']);
  await expect(page.getByRole('link', {name: 'Administration', exact: true})).toHaveCount(0);
  expect((await page.request.get('/api/admin/workspace')).status()).toBe(403);
});

test('registration handles password mismatch and duplicate email, and fits mobile', async ({ page }) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/register/student-parent');
  await expect(page.getByRole('heading', {name: 'Student & parent registration'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({path: 'test-results/registration-mobile.png', fullPage: true});
  await fillRegistration(page, 'duplicate-browser@example.com');
  await page.getByLabel('Confirm password').fill('DifferentPassphrase!2026');
  await page.getByRole('button', {name: 'Create account', exact: true}).click();
  await expect(page.getByRole('alert')).toHaveText('Passwords do not match.');
  await page.getByLabel('Confirm password').fill('PersonalPassphrase!2026');
  await page.getByRole('button', {name: 'Create account', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Account created', exact: true})).toBeVisible();
  await page.reload();
  await fillRegistration(page, 'DUPLICATE-browser@example.com');
  await page.getByRole('button', {name: 'Create account', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('An account with this email already exists.');
  await page.setViewportSize({width: 1440, height: 1100});
  await page.goto('/register/other');
  await page.screenshot({path: 'test-results/registration-desktop.png', fullPage: true});
});
