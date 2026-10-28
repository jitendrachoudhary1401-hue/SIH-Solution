import { expect, test } from './fixtures';

test('first privileged sign-in completes MFA and saves recovery codes before opening the workspace', async ({ page }) => {
  let enabled = false;
  const calls: string[] = [];
  const user = { id: 999, name: 'Synthetic Administrator', email: 'audit@example.test', role: 'admin',
    is_demo: false, requested_role: null, organization: '', approval_pending: false,
    bureau_id: null, bureau: 'Assigned scope', roles: ['admin'], capabilities: { admin: true, cases: true } };
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    calls.push(path);
    let body: unknown;
    if (path === '/api/wake') body = { status: 'awake', service: 'onecase' };
    else if (path === '/api/auth/me') body = { user: { ...user, mfa_enrollment_required: !enabled }, csrf: 'synthetic-test-csrf' };
    else if (path === '/api/auth/mfa/setup') body = { secret: 'SYNTHETIC-TEST-KEY', uri: '' };
    else if (path === '/api/auth/mfa/confirm') { enabled = true; body = { csrf: 'synthetic-rotated-csrf', recovery_codes: ['audit-code-01', 'audit-code-02'] }; }
    else if (path === '/api/admin/workspace') body = { users: [], roles: [], operations: [], permissions: [], appointments: [], role_assignments: [], security_events: [] };
    else if (path === '/api/operations') body = { jobs: {}, oldest_queued_at: null };
    else if (path === '/api/directory') body = { bureaus: [], officers: [], participants: [], categories: [], deadline_rules: [] };
    else body = { items: [], total: 0, asOf: new Date().toISOString() };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Set up your authenticator' })).toBeVisible();
  expect(calls).not.toContain('/api/admin/workspace');
  await page.getByRole('button', { name: 'Set up authenticator', exact: true }).click();
  await page.getByLabel('Authenticator code').fill('123456');
  await page.getByRole('button', { name: 'Verify and enable MFA' }).click();
  await expect(page.getByText('audit-code-01', { exact: true })).toBeVisible();
  expect(calls).not.toContain('/api/admin/workspace');
  await page.getByRole('button', { name: 'I saved my codes — continue' }).click();
  await expect(page.getByRole('heading', { name: 'Access, with accountability' })).toBeVisible();
});
