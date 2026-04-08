# TASK: Stripe Billing 통합

> 담당: 코드2
> 우선순위: P1

---

## 배경

ContentFlow는 SaaS 제품으로 가는 중이다. 지금까지 인증, 사용량 추적, 플랜별 한도까지 구현했지만 **실제 결제 처리**가 빠져있다. 이 작업은 Stripe를 통합해 유료 플랜 결제를 가능하게 만든다.

---

## 작업 1: Stripe SDK 통합

### 파일: `app/services/billing_service.py`

Stripe Python SDK 기반 결제 서비스:

- `create_customer(user)` — Stripe customer 생성
- `create_checkout_session(user, plan)` — Checkout 세션 생성
- `create_portal_session(user)` — 고객 포털 (구독 관리)
- `cancel_subscription(user)` — 구독 취소
- `change_plan(user, new_plan)` — 플랜 변경
- `get_subscription_status(user)` — 구독 상태 조회

플랜 매핑:
- Free: 결제 없음
- Build: $29/월 (Stripe Price ID: price_build_monthly)
- Scale: $79/월 (Stripe Price ID: price_scale_monthly)
- Enterprise: $299/월 (Stripe Price ID: price_enterprise_monthly)

연간 결제는 20% 할인 (price_*_yearly).

---

## 작업 2: Billing API

### 파일: `app/api/v1/billing.py`

- `POST /api/v1/billing/checkout` — 결제 시작
  - 입력: `plan` (build/scale/enterprise), `interval` (monthly/yearly)
  - 출력: Stripe Checkout URL
  
- `POST /api/v1/billing/portal` — 고객 포털 접속
  - 출력: Stripe Customer Portal URL

- `GET /api/v1/billing/subscription` — 현재 구독 정보
  - 출력: plan, status, current_period_end, cancel_at_period_end

- `POST /api/v1/billing/cancel` — 구독 취소 (current period 끝까지 유지)

- `POST /api/v1/billing/change-plan` — 플랜 변경

---

## 작업 3: Stripe Webhook 처리

### 파일: `app/api/webhooks/stripe.py`

Stripe webhook 이벤트 처리:

- `checkout.session.completed` — 결제 완료 → user.plan 업데이트
- `customer.subscription.updated` — 구독 변경 (플랜 업/다운그레이드)
- `customer.subscription.deleted` — 구독 취소
- `invoice.payment_failed` — 결제 실패 → 알림 + grace period
- `invoice.payment_succeeded` — 결제 성공 → 사용량 리셋

웹훅 서명 검증 필수 (`stripe.Webhook.construct_event`).

엔드포인트: `POST /api/webhooks/stripe`

---

## 작업 4: DB 스키마 추가

### 파일: `app/models/schemas.py`

users 테이블 확장:
- `stripe_customer_id` (TEXT)
- `stripe_subscription_id` (TEXT)
- `subscription_status` (TEXT) — active, past_due, canceled, trialing
- `current_period_end` (TIMESTAMPTZ)
- `cancel_at_period_end` (BOOLEAN)

신규 테이블 `payments`:
- id, user_id, stripe_invoice_id, amount, currency, status, paid_at, created_at

신규 테이블 `subscription_events`:
- id, user_id, event_type, from_plan, to_plan, metadata (JSONB), created_at

---

## 작업 5: 환경 변수

`.env.example`에 추가:
```
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_BUILD_MONTHLY=price_xxx
STRIPE_PRICE_BUILD_YEARLY=price_xxx
STRIPE_PRICE_SCALE_MONTHLY=price_xxx
STRIPE_PRICE_SCALE_YEARLY=price_xxx
STRIPE_PRICE_ENTERPRISE_MONTHLY=price_xxx
STRIPE_PRICE_ENTERPRISE_YEARLY=price_xxx
STRIPE_SUCCESS_URL=https://contentflow.dev/billing/success
STRIPE_CANCEL_URL=https://contentflow.dev/billing/cancel
```

---

## 작업 6: 결제 실패 처리

`app/workers/billing_worker.py`:
- 결제 실패 시 3일 grace period 부여
- grace period 후에도 결제 안 되면 plan을 free로 다운그레이드
- 다운그레이드 전 이메일 알림 (TODO 주석으로 남기기)
- Celery Beat로 매일 1회 실행

---

## 작업 7: 테스트

- `tests/test_billing.py`
  - Stripe SDK는 mock 사용
  - Checkout session 생성
  - Webhook 이벤트 처리 (서명 검증 포함)
  - 플랜 변경 플로우
  - 구독 취소
  - 결제 실패 → grace period

---

## 완료 기준

- [ ] Stripe SDK 통합
- [ ] Billing API 5개 엔드포인트
- [ ] Stripe webhook handler + 서명 검증
- [ ] DB 스키마 확장 (users + payments + subscription_events)
- [ ] 환경 변수 추가
- [ ] 결제 실패 worker
- [ ] 테스트 추가
- [ ] ruff + pytest 통과

---

## 참고

Stripe 테스트 키는 `sk_test_` 시작.
실제 결제 안 되니까 mock으로 충분히 검증 가능.
프로덕션은 사장님이 직접 Stripe 계정 만들고 라이브 키 발급받아야 함.
