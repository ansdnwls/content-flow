# TASK: E2E 테스트 + 품질 검증 자동화

> 담당: 코드3
> 우선순위: P0 (출시 전 필수)

---

## 배경

지금 ContentFlow는 **단위 테스트 647개**가 통과하지만, 실제 사용자 플로우 전체가 동작하는지는 검증이 안 됐다.

"포스트 목록 페이지가 로딩된다" + "포스트 생성 API가 성공을 반환한다" 각각 통과해도, **사용자가 대시보드에서 포스트를 생성하면 DB에 저장되고 화면에 표시되는지**는 별개 이야기다.

이 작업은 Playwright로 **사용자 관점 E2E 테스트**를 구축하는 것이다.

---

## 작업 1: Playwright 셋업

### 디렉토리: `e2e/`

```
e2e/
├── playwright.config.ts
├── tests/
│   ├── auth/
│   │   ├── signup.spec.ts
│   │   ├── login.spec.ts
│   │   └── email-verify.spec.ts
│   ├── posts/
│   │   ├── create.spec.ts
│   │   ├── list.spec.ts
│   │   ├── schedule.spec.ts
│   │   └── bulk.spec.ts
│   ├── videos/
│   │   ├── generate.spec.ts
│   │   └── auto-publish.spec.ts
│   ├── accounts/
│   │   ├── connect-youtube.spec.ts
│   │   └── disconnect.spec.ts
│   ├── analytics/
│   │   └── dashboard.spec.ts
│   ├── billing/
│   │   ├── upgrade.spec.ts
│   │   └── cancel.spec.ts
│   └── i18n/
│       └── language-switch.spec.ts
├── fixtures/
│   ├── test-users.ts
│   ├── test-data.ts
│   └── mock-oauth.ts
├── helpers/
│   ├── auth-helper.ts
│   └── api-helper.ts
└── package.json
```

```bash
cd e2e
npm init -y
npm install --save-dev @playwright/test
npx playwright install
```

---

## 작업 2: 핵심 플로우 테스트

### 2.1 가입 → 첫 포스팅 플로우 (가장 중요)

```typescript
test('user can sign up and create first post', async ({ page }) => {
  // 1. 랜딩페이지 → 가입
  await page.goto('/');
  await page.click('text=Get started');
  await page.fill('[name=email]', `test-${Date.now()}@example.com`);
  await page.fill('[name=password]', 'SecurePass123!');
  await page.click('button:has-text("Sign up")');
  
  // 2. 이메일 인증 (mock)
  // API로 직접 verify_email 호출
  
  // 3. 대시보드 진입
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.locator('h1')).toContainText('Welcome');
  
  // 4. YouTube 계정 연결 (mock OAuth)
  await page.click('text=Connect account');
  await page.click('text=YouTube');
  // Mock OAuth callback
  
  // 5. 첫 포스트 작성
  await page.click('text=New Post');
  await page.fill('[name=text]', 'My first post via ContentFlow');
  await page.check('[value=youtube]');
  await page.click('button:has-text("Publish")');
  
  // 6. 성공 확인
  await expect(page.locator('.toast')).toContainText('Published');
});
```

### 2.2 영상 생성 → 자동 배포

```typescript
test('user can generate video and auto-publish', async ({ page }) => {
  await loginAsTestUser(page);
  
  await page.goto('/dashboard/videos/new');
  await page.fill('[name=topic]', 'How DUI laws work');
  await page.selectOption('[name=mode]', 'legal');
  await page.selectOption('[name=language]', 'ko');
  await page.selectOption('[name=format]', 'shorts');
  await page.check('[name=auto_publish]');
  await page.check('[value=youtube]');
  await page.click('button:has-text("Generate")');
  
  // 진행 상태 확인
  await expect(page.locator('.progress')).toBeVisible();
  
  // 완료 대기 (mock에서는 즉시)
  await expect(page.locator('.status')).toContainText('Completed', { timeout: 30000 });
});
```

### 2.3 결제 플로우 (Stripe Checkout)

```typescript
test('user can upgrade to Build plan', async ({ page }) => {
  await loginAsTestUser(page);
  
  await page.goto('/dashboard/billing');
  await page.click('text=Upgrade to Build');
  
  // Stripe Checkout은 외부 도메인이라 mock 사용
  // stripe-mock 컨테이너 또는 테스트 모드 키
  
  // Mock 결제 성공 후 리다이렉트
  await page.goto('/dashboard/billing/success?session_id=cs_test_123');
  
  await expect(page.locator('.plan-badge')).toContainText('Build');
});
```

### 2.4 웹훅 설정

```typescript
test('user can configure webhook and see deliveries', async ({ page }) => {
  await loginAsTestUser(page);
  
  await page.goto('/dashboard/webhooks');
  await page.click('text=Add webhook');
  await page.fill('[name=url]', 'https://example.com/webhook');
  await page.check('[value=post.published]');
  await page.click('button:has-text("Save")');
  
  // 웹훅 목록에 표시 확인
  await expect(page.locator('.webhook-item')).toContainText('example.com');
  
  // 수동 테스트 전송
  await page.click('text=Test');
  await expect(page.locator('.delivery-status')).toContainText('Delivered');
});
```

### 2.5 언어 전환

```typescript
test('user can switch language', async ({ page }) => {
  await loginAsTestUser(page);
  
  await page.click('.language-switcher');
  await page.click('text=한국어');
  
  await expect(page).toHaveURL(/\/ko\//);
  await expect(page.locator('nav')).toContainText('포스트');
});
```

---

## 작업 3: API E2E 테스트

### 파일: `e2e/api/`

백엔드 API 플로우도 E2E로 검증:

```typescript
test('complete API workflow', async ({ request }) => {
  // 1. API key 발급 (admin 키로)
  const keyResponse = await request.post('/api/v1/keys', {
    headers: { 'Authorization': `Bearer ${process.env.TEST_API_KEY}` },
  });
  const { key } = await keyResponse.json();
  
  // 2. 웹훅 등록
  const webhook = await request.post('/api/v1/webhooks', {
    headers: { 'Authorization': `Bearer ${key}` },
    data: { url: 'https://webhook.site/...', events: ['post.published'] },
  });
  
  // 3. 포스트 생성
  const post = await request.post('/api/v1/posts', {
    headers: { 'Authorization': `Bearer ${key}` },
    data: {
      text: 'E2E test post',
      platforms: ['youtube'],
      dry_run: true,
    },
  });
  
  expect(post.ok()).toBe(true);
  
  // 4. 웹훅 호출 확인 (webhook.site API로)
  await waitForWebhook(webhook.id);
});
```

---

## 작업 4: 시각적 회귀 테스트

### 파일: `e2e/visual/`

```typescript
test('dashboard home matches screenshot', async ({ page }) => {
  await loginAsTestUser(page);
  await page.goto('/dashboard');
  await expect(page).toHaveScreenshot('dashboard-home.png', {
    maxDiffPixels: 100,
  });
});
```

대상 페이지:
- 랜딩페이지 (hero, 가격, 피처)
- 로그인 / 가입
- 대시보드 홈
- 포스트 목록
- 새 포스트 작성
- 분석 대시보드
- 설정

다크/라이트 모드 둘 다 캡처.
모바일 뷰포트도 별도.

---

## 작업 5: 성능 테스트 (E2E)

### 파일: `e2e/performance/`

Playwright로 성능 지표 측정:

```typescript
test('dashboard loads within 2 seconds', async ({ page }) => {
  const start = Date.now();
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  const loadTime = Date.now() - start;
  expect(loadTime).toBeLessThan(2000);
});

test('LCP under 2.5 seconds', async ({ page }) => {
  await page.goto('/');
  
  const lcp = await page.evaluate(() => {
    return new Promise(resolve => {
      new PerformanceObserver(list => {
        const entries = list.getEntries();
        resolve(entries[entries.length - 1].startTime);
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    });
  });
  
  expect(lcp).toBeLessThan(2500);
});
```

---

## 작업 6: 접근성 테스트

### 파일: `e2e/a11y/`

`@axe-core/playwright` 사용:

```typescript
import AxeBuilder from '@axe-core/playwright';

test('dashboard has no accessibility violations', async ({ page }) => {
  await page.goto('/dashboard');
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
```

모든 주요 페이지에 적용.

---

## 작업 7: CI 통합

### 파일: `.github/workflows/e2e.yml`

```yaml
name: E2E Tests

on: [pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    services:
      postgres: ...
      redis: ...
    steps:
      - uses: actions/checkout@v4
      - name: Start backend
        run: docker compose up -d
      - name: Wait for backend
        run: ./scripts/wait_for_api.sh
      - name: Install Playwright
        working-directory: e2e
        run: npm ci && npx playwright install
      - name: Run E2E tests
        working-directory: e2e
        run: npx playwright test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: e2e/playwright-report/
```

---

## 작업 8: Mock 서비스

### 파일: `e2e/mocks/`

외부 서비스 mock:

- `mock-oauth.ts` — OAuth 프로바이더 mock (Google, Meta, TikTok, X, LinkedIn)
- `mock-stripe.ts` — Stripe Checkout mock 또는 stripe-mock 컨테이너
- `mock-youtube.ts` — YouTube upload mock
- `mock-webhooks.ts` — webhook.site 또는 로컬 서버

E2E 테스트는 **실제 외부 API 호출 금지**. 모두 mock으로.

---

## 작업 9: 테스트 데이터 시드

### 파일: `e2e/fixtures/seed.sql`

각 테스트 실행 전 DB에 시드 데이터:
- 테스트 유저 3명 (free/build/scale 플랜)
- 각 유저마다 API key
- 샘플 posts, videos
- Mock social accounts

### 파일: `e2e/fixtures/cleanup.sh`
- 테스트 후 DB 정리
- 특정 prefix 데이터만 삭제 (`test_%`)

---

## 작업 10: 테스트 리포트

### 파일: `e2e/playwright.config.ts`

```typescript
export default defineConfig({
  reporter: [
    ['html'],
    ['list'],
    ['json', { outputFile: 'results.json' }],
    ['github'],
  ],
  use: {
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
});
```

실패 시:
- 스크린샷 자동 저장
- 비디오 녹화
- 네트워크 트레이스
- Playwright UI 리포트

---

## 완료 기준

- [ ] Playwright 셋업 (`e2e/`)
- [ ] 핵심 플로우 5개 테스트 (가입→포스팅, 영상, 결제, 웹훅, 언어)
- [ ] API E2E 테스트
- [ ] 시각적 회귀 테스트 (주요 페이지 스크린샷)
- [ ] 성능 테스트 (LCP, 로딩 시간)
- [ ] 접근성 테스트 (axe)
- [ ] CI 통합 (.github/workflows/e2e.yml)
- [ ] Mock 서비스 (OAuth, Stripe, YouTube)
- [ ] 시드/클린업 스크립트
- [ ] 테스트 리포트 설정
- [ ] 모든 E2E 테스트 통과

---

## 의미

단위 테스트는 "각 부품이 작동하는가"를 검증한다.
E2E 테스트는 **"사용자가 진짜 사용할 수 있는가"**를 검증한다.

프로덕션 출시 후 가장 흔한 사고:
- 단위 테스트는 다 통과했는데
- 실제 사용자가 가입하자마자 에러
- 프론트-백엔드 통합 지점에서 발생

이걸 사전에 잡는 게 E2E의 목적이다.

특히 **"가입 → 첫 포스팅 성공"** 플로우는 ContentFlow의 핵심 지표다. 이 플로우가 CI에서 매일 검증되면, 실수로 이걸 깨뜨리는 코드가 merge되기 전에 막힌다.
