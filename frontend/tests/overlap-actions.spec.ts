import { test, expect, type Page } from './fixtures';

async function signIn(page: Page) {
  await page.goto('/officer/login');
  await page.getByLabel('Email address').fill('lead.rb@onecase.demo');
  await page.getByLabel('Password', { exact: true }).fill('OneCaseDemo!2026');
  await page.getByRole('button', { name: 'Sign in to workspace' }).click();
  await expect(page.getByRole('heading', { name: /Good / })).toBeVisible();
}

async function complaint(page: Page, location: string, description: string) {
  const identity = await (await page.request.get('/api/auth/me')).json();
  const response = await page.request.post('/api/complaints', {
    headers: { 'X-CSRF-Token': identity.csrf, 'Idempotency-Key': crypto.randomUUID() },
    data: { institution_id: 1, owner_id: identity.user.id, incident_location: location,
      category: 'Fee refund', description, issue_summary: 'Unpaid refund after timely withdrawal',
      received_at: new Date().toISOString(), next_action: 'Review receipt and withdrawal record' },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

test('same issue at another location is excluded; officer can reject all suggestions', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await signIn(page);
  const location = `North campus accounts room ${crypto.randomUUID()}`;
  const description = 'The college has still not returned my tuition deposit after timely withdrawal despite written reminders and acknowledgement of all payment documents.';
  const first = await complaint(page, location, description);
  const different = await complaint(page, 'South campus ' + crypto.randomUUID(), description);
  await page.goto('/alerts');
  await expect(page.getByRole('heading', { name: 'Alerts', exact: true })).toBeVisible();
  await expect(page.locator('.overlap-group').filter({ hasText: different.reference })).toHaveCount(0);
  const second = await complaint(page, location, description);
  await page.getByRole('button', { name: 'Check overlaps now' }).click();
  const group = page.locator('.overlap-group').filter({ hasText: first.reference });
  await expect(group).toContainText(second.reference);
  await page.setViewportSize({width:390, height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/overlap-alert-mobile.png',fullPage:true});
  await group.getByRole('button', { name: 'Reject all', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Reject overlap suggestions' });
  await dialog.getByLabel('Decision reason').fill('These are separate incidents despite similar wording and location.');
  await dialog.getByRole('button', { name: 'Confirm reject all' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(group).toHaveCount(0);
  expect((await (await page.request.get(`/api/complaints/${first.id}`)).json()).status).toBe('received');
  expect(errors).toEqual([]);
});

test('officer merges a connected group, sees original records and downloads a PDF', async ({ page }) => {
  await signIn(page);
  const location = `West campus records office ${crypto.randomUUID()}`;
  const description = 'The finance office has not returned the admission deposit after cancellation within the permitted period. Written requests and payment receipts remain unanswered.';
  const first = await complaint(page, location, description);
  const second = await complaint(page, location, description);
  await page.goto('/overlaps');
  const group = page.locator('.overlap-group').filter({ hasText: first.reference });
  await expect(group).toContainText(second.reference);
  await group.getByRole('button', { name: 'Merge all', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Merge overlapping complaints' });
  await dialog.getByLabel('Primary complaint').selectOption(String(first.id));
  await dialog.getByLabel('Decision reason').fill('Same incident, payment reference, issue and location verified against the complaints.');
  await dialog.getByRole('button', { name: 'Confirm merge all' }).click();
  await expect(dialog).not.toBeVisible();
  await page.goto(`/complaints/${first.id}`);
  await expect(page.getByText(/Coordination group #/)).toBeVisible();
  await expect(page.locator('.coordination-notice')).toContainText(second.reference);
  await page.goto('/complaints');
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export PDF', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('onecase-complaints.pdf');
});
