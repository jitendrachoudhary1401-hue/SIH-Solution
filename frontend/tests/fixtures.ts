import { test as base, expect } from '@playwright/test';

// The suite shares one disposable backend. Isolate authentication attempt
// counters per scenario, while leaving the production protection unchanged.
export const test = base.extend<{ isolatedAuthAttempts: void }>({
  isolatedAuthAttempts: [async ({ request }, use) => {
    const response = await request.post('/api/test-only/reset-auth-attempts', {
      data: { fixture: 'isolated-browser-test' },
    });
    expect(response.ok()).toBeTruthy();
    await use();
  }, { auto: true }],
});
export { expect };
export type { Page } from '@playwright/test';
