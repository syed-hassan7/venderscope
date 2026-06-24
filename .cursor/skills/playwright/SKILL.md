---
name: playwright
description: Write and run Playwright end-to-end browser tests. Use when asked to "test this in a browser", "write e2e tests", "verify the user flow works", "test if rate limiting works", or "check the UI behaves correctly".
---

You are a senior QA engineer using Playwright to test web applications in real browsers (Chromium, Firefox, WebKit).

## Project Setup (run once)
```bash
npm init playwright@latest
# Select: TypeScript, tests/ directory, add GitHub Actions workflow, install browsers
```

## Core Test Patterns

### User Authentication Flow
```typescript
import { test, expect } from '@playwright/test'

test('complete auth flow: register, login, logout', async ({ page }) => {
  // Register
  await page.goto('/register')
  await page.fill('[name="email"]', `test+${Date.now()}@example.com`)
  await page.fill('[name="password"]', 'SecurePass123!')
  await page.fill('[name="confirmPassword"]', 'SecurePass123!')
  await page.click('[type="submit"]')
  await expect(page).toHaveURL('/dashboard')

  // Logout
  await page.click('[data-testid="logout-btn"]')
  await expect(page).toHaveURL('/login')

  // Verify session destroyed — cannot access protected route
  await page.goto('/dashboard')
  await expect(page).toHaveURL('/login')
})
```

### Security Tests — Rate Limiting
```typescript
test('login rate limit triggers after 5 failed attempts', async ({ page }) => {
  for (let i = 0; i < 6; i++) {
    await page.goto('/login')
    await page.fill('[name="email"]', 'victim@example.com')
    await page.fill('[name="password"]', `wrongpassword${i}`)
    await page.click('[type="submit"]')
    await page.waitForLoadState('networkidle')
  }
  // Should see rate limit message
  await expect(page.getByText(/too many|rate limit|try again/i)).toBeVisible()
})
```

### Security Tests — IDOR Protection
```typescript
test('user cannot access another users private data', async ({ browser }) => {
  // Create two isolated browser contexts (two separate users)
  const contextA = await browser.newContext()
  const contextB = await browser.newContext()
  const pageA = await contextA.newPage()
  const pageB = await contextB.newPage()

  // Log in as User A and get a resource ID
  await loginAs(pageA, 'userA@example.com', 'password')
  await pageA.goto('/dashboard')
  const resourceUrl = await pageA.locator('[data-testid="first-item"]').getAttribute('href')

  // Log in as User B and attempt to access User A's resource
  await loginAs(pageB, 'userB@example.com', 'password')
  await pageB.goto(resourceUrl!)

  // Should be redirected or shown 404 — never the actual data
  await expect(pageB).not.toHaveURL(resourceUrl!)

  await contextA.close()
  await contextB.close()
})
```

### Protected Route Tests
```typescript
test('unauthenticated users cannot access protected routes', async ({ page }) => {
  const protectedRoutes = ['/dashboard', '/account', '/admin', '/settings', '/api/user']

  for (const route of protectedRoutes) {
    await page.goto(route)
    // Should redirect to login, not show the page
    await expect(page).not.toHaveURL(route)
  }
})

test('regular users cannot access admin routes', async ({ page }) => {
  await loginAs(page, 'regular@example.com', 'password')
  await page.goto('/admin')
  // Should get 403 or redirect — never the admin panel
  const status = page.url()
  expect(status).not.toContain('/admin')
})
```

### Form Validation Tests
```typescript
test('forms display correct validation errors', async ({ page }) => {
  await page.goto('/register')
  await page.click('[type="submit"]') // submit empty form

  await expect(page.getByText(/email is required/i)).toBeVisible()
  await expect(page.getByText(/password is required/i)).toBeVisible()

  // Test weak password
  await page.fill('[name="password"]', '123')
  await page.click('[type="submit"]')
  await expect(page.getByText(/password must be/i)).toBeVisible()
})
```

## Helper Functions (add to tests/helpers.ts)
```typescript
export async function loginAs(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.fill('[name="email"]', email)
  await page.fill('[name="password"]', password)
  await page.click('[type="submit"]')
  await page.waitForURL('/dashboard')
}
```

## Running Tests
```bash
npx playwright test                      # headless, all browsers
npx playwright test --ui                 # visual test runner (recommended for debugging)
npx playwright test --headed             # watch tests run in real browser
npx playwright test --project=chromium  # single browser
npx playwright test auth.spec.ts         # single file
npx playwright show-report               # open HTML report after run
```

## Mandatory Test Checklist per Project
- [ ] User registration with valid and invalid data
- [ ] Login with correct credentials succeeds
- [ ] Login with wrong credentials fails with correct message
- [ ] Rate limiting triggers after repeated failed login
- [ ] Protected routes redirect unauthenticated users to login
- [ ] IDOR: authenticated user cannot access another user's resources
- [ ] Admin routes inaccessible to regular users
- [ ] Forms show validation errors for invalid input
- [ ] Core user journey works end to end (the most important flow in the app)
- [ ] Logout destroys session and blocks access to protected routes
