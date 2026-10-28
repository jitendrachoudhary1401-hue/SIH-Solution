import { test, expect, type Page } from './fixtures';

async function signIn(page: Page, email = 'lead.rb@onecase.demo') {
  await page.goto('/officer/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill('OneCaseDemo!2026');
  await page.getByRole('button', { name: 'Sign in to workspace' }).click();
  await expect(page.getByRole('heading', { name: /Good / })).toBeVisible();
}

test('officer creates, acts on, disposes, reopens, and transfers a case', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await signIn(page);
  await page.getByRole('button', { name: 'New complaint' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Institution', { exact: true }).selectOption('1');
  await dialog.getByLabel('Incident location', {exact: true}).fill('Synthetic main campus, accounts office');
  await dialog.getByLabel('Complaint description').fill('The student withdrew within the permitted window but the institution has not returned the fee deposit. Written reminders remain unanswered.');
  await dialog.getByLabel('Next action').fill('Request the fee refund ledger');
  await dialog.getByLabel('Illustrative deadline rule').selectOption('demo-business-v1');
  await dialog.getByRole('button', { name: 'Register complaint' }).click();
  await expect(page.getByRole('heading', { name: /^OC-/ })).toBeVisible();
  const reference = await page.getByRole('heading', { name: /^OC-/ }).innerText();
  await page.getByRole('button', { name: 'Record action', exact: true }).click();
  await dialog.getByLabel('Action / remark').fill('The officer requested the withdrawal acknowledgement from the institution.');
  await dialog.getByRole('button', { name: 'Save to case history' }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole('tab', { name: 'History' }).click();
  await expect(page.getByText('Officer action recorded', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Upload supporting evidence').setInputFiles('tests/fixtures/synthetic-outcome.png');
  const uploaded = page.waitForResponse(r => r.url().endsWith('/attachments') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Upload evidence', exact: true }).click();
  expect((await uploaded).status()).toBe(201);
  await expect(page.getByRole('link', { name: 'Download', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Change status', exact: true }).click();
  await dialog.getByLabel('New status').selectOption('disposed');
  await dialog.getByLabel('Outcome document', {exact:true}).selectOption({label:'synthetic-outcome.png'});
  await dialog.getByLabel('Communication record', {exact:true}).fill('Outcome communicated to the synthetic complainant through recorded correspondence.');
  await dialog.getByLabel('Reason', { exact: true }).fill('Refund has been documented and accepted by the complainant.');
  await dialog.getByRole('button', { name: 'Save to case history' }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole('button', { name: 'Change status', exact: true }).click();
  await dialog.getByLabel('New status').selectOption('under_review');
  await dialog.getByLabel('Reason', { exact: true }).fill('New evidence requires reopening and additional review.');
  await dialog.getByRole('button', { name: 'Save to case history' }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole('button', { name: 'Transfer case' }).click();
  await dialog.getByLabel('Receiving accountable officer').selectOption('3');
  await dialog.getByLabel('Reason', { exact: true }).fill('PGRC should coordinate the refund follow-up.');
  await dialog.getByRole('button', { name: 'Confirm transfer' }).click();
  await expect(page).toHaveURL(/\/complaints$/);
  await expect(page.getByText(reference, { exact: true })).not.toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to OneCase' })).toBeVisible();
  await signIn(page, 'lead.pgrc@onecase.demo');
  await page.getByRole('link', { name: 'Complaints', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Complaints', exact: true })).toBeVisible();
  await page.getByRole('table').getByRole('link', { name: reference, exact: true }).click();
  await page.getByRole('button', { name: 'Acknowledge transfer' }).click();
  await expect(page.getByRole('button', { name: 'Acknowledge transfer' })).not.toBeVisible();
  expect(errors).toEqual([]);
});

test('responsive workspace and keyboard navigation at mobile, tablet and desktop', async ({ page }) => {
  await signIn(page);
  for (const width of [360, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole('heading', { name: /Good / })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (width === 360) {
      await page.getByRole('button', { name: 'Open navigation' }).click();
      await expect(page.getByRole('dialog', { name: 'Workspace navigation' })).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog', { name: 'Workspace navigation' })).not.toBeVisible();
    }
    await page.screenshot({ path: `test-results/dashboard-${width}.png`, fullPage: true });
  }
  await expect(page.getByRole('button', {name:'Use dark theme'})).toHaveCount(0);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  expect(await page.locator('body').evaluate(element=>parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(16);
  await page.getByRole('link', { name: 'Action logs', exact: true }).click();
  await page.getByRole('button', { name: /Complaint registered/ }).first().click();
  await expect(page.getByText('Original UTC timestamp').first()).toBeVisible();
  await page.getByRole('link', { name: 'Institutions', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Institutions', exact: true })).toBeVisible();
  await page.getByRole('link', { name: /Northstar Institute/ }).click();
  await expect(page.getByRole('heading', { name: 'Permitted complaint history' })).toBeVisible();
});

test('direct API access is scoped and rejects missing CSRF', async ({ page }) => {
  await signIn(page);
  const denied = await page.request.get('/api/complaints/2');
  expect(denied.status()).toBe(404);
  const csrf = await page.request.post('/api/complaints/1/actions', { data: { version: 1, reason: 'Invalid token test' } });
  expect(csrf.status()).toBe(403);
});

test('reviewer compares real model evidence and records a decision', async ({ page }) => {
  test.skip(process.env.E2E_MATCHING !== '1', 'Run with E2E_MATCHING=1 after downloading local models.');
  await signIn(page, 'reviewer@onecase.demo');
  await page.getByRole('link', { name: 'Overlap review', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Overlap review', exact: true })).toBeVisible();
  await page.locator('a.pair-card').filter({ hasText: 'OC-2026-00001' }).filter({ hasText: 'OC-2026-00002' }).click();
  await expect(page.getByRole('heading', { name: 'Possible overlap' })).toBeVisible();
  await expect(page.getByText('Cross-Encoder raw logit')).toBeVisible();
  await page.getByLabel('Decision', { exact: true }).selectOption('related');
  await page.getByLabel('Reason', { exact: true }).fill('Both records describe the same withheld tuition refund after timely withdrawal.');
  await page.getByRole('button', { name: 'Record decision' }).click();
  await expect(page.getByText('Riya Menon', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('Both records describe the same withheld tuition refund after timely withdrawal.')).toBeVisible();
});
