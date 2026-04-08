# TASK: 이메일 알림 + 온보딩 시스템

> 담당: 코드2
> 우선순위: P1

---

## 배경

Stripe 결제, API Key, OAuth 연결, 웹훅 실패 등 사용자에게 알려야 할 이벤트가 많은데 지금은 이메일 발송 시스템이 없다. 이 작업은 이메일 인프라를 구축하고 주요 이벤트마다 알림을 보내게 만든다.

또한 신규 사용자 온보딩 플로우도 함께 구현한다.

---

## 작업 1: 이메일 서비스

### 파일: `app/services/email_service.py`

Resend SDK 기반 (또는 SendGrid). Resend가 개발자 친화적이라 추천.

기능:
- `send_email(to, subject, html, text=None, tags=None)` — 단건 발송
- `send_template(template_id, to, variables)` — 템플릿 발송
- `send_batch(messages)` — 대량 발송 (최대 100건)
- 발송 실패 시 재시도 (Celery)
- 발송 로그 저장

DB 추가 (`app/models/schemas.py`):

신규 테이블 `email_logs`:
- id, user_id, to_email, subject, template, status, error, sent_at, created_at

---

## 작업 2: 이메일 템플릿

### 파일: `app/templates/emails/`

HTML + 텍스트 버전 둘 다 작성:

1. **welcome.html** — 가입 환영
   - 변수: name, dashboard_url, docs_url
   
2. **email_verify.html** — 이메일 인증
   - 변수: name, verify_url
   
3. **api_key_created.html** — API Key 발급 알림
   - 변수: name, key_prefix, created_at, ip
   
4. **payment_succeeded.html** — 결제 성공
   - 변수: name, amount, plan, invoice_url
   
5. **payment_failed.html** — 결제 실패
   - 변수: name, amount, retry_url, grace_period_days
   
6. **subscription_canceled.html** — 구독 취소
   - 변수: name, plan, period_end
   
7. **plan_upgraded.html** — 플랜 업그레이드
   - 변수: name, old_plan, new_plan
   
8. **account_disconnected.html** — 소셜 계정 토큰 만료
   - 변수: name, platform, reconnect_url
   
9. **webhook_failing.html** — 웹훅 연속 실패
   - 변수: name, webhook_url, failure_count
   
10. **monthly_summary.html** — 월간 사용량 요약
    - 변수: name, posts_count, videos_count, top_platforms

워크스페이스 브랜딩 적용:
- logo, primary_color, support_email 자동 치환
- white-label 활성화 시 ContentFlow 브랜딩 제거

---

## 작업 3: 이벤트 트리거

각 이벤트에 이메일 발송 연결:

### Auth & API Keys
- 사용자 가입 → welcome
- 이메일 미인증 → email_verify
- API Key 발급 → api_key_created
- API Key 회전 → api_key_rotated

### Billing
- checkout.session.completed → payment_succeeded
- invoice.payment_failed → payment_failed
- subscription canceled → subscription_canceled
- plan upgraded → plan_upgraded

### OAuth
- 토큰 만료 → account_disconnected

### Webhooks
- 5회 연속 실패 → webhook_failing

### Periodic
- 매월 1일 → monthly_summary (Celery Beat)

---

## 작업 4: 온보딩 플로우 API

### 파일: `app/api/v1/onboarding.py`

신규 사용자가 첫 API 호출까지 가는 길을 안내:

- `GET /api/v1/onboarding/status` — 현재 진행 단계
  ```json
  {
    "steps": [
      {"id": "verify_email", "completed": true},
      {"id": "create_api_key", "completed": true},
      {"id": "connect_first_account", "completed": false},
      {"id": "first_post", "completed": false},
      {"id": "first_video", "completed": false}
    ],
    "progress": 40
  }
  ```

- `POST /api/v1/onboarding/skip/{step}` — 단계 건너뛰기
- `POST /api/v1/onboarding/complete` — 온보딩 완료 처리

### DB 추가
users 테이블에:
- `email_verified` (BOOLEAN)
- `email_verified_at` (TIMESTAMPTZ)
- `onboarding_completed` (BOOLEAN)
- `onboarding_steps` (JSONB)

---

## 작업 5: 이메일 인증 플로우

- `POST /api/v1/auth/verify-email/request` — 인증 메일 발송
- `POST /api/v1/auth/verify-email/confirm` — 토큰으로 인증 완료
- 인증 토큰은 JWT로 24시간 유효
- 인증 안 된 사용자도 API는 사용 가능 (강제 아님)

---

## 작업 6: Unsubscribe 시스템

### 파일: `app/api/v1/notifications.py`

- `GET /api/v1/notifications/preferences` — 알림 설정 조회
- `PATCH /api/v1/notifications/preferences` — 알림 on/off
  - product_updates, billing, security, monthly_summary, webhook_alerts

이메일 푸터에 unsubscribe 링크 자동 포함.

---

## 작업 7: 환경 변수

`.env.example`에 추가:
```
RESEND_API_KEY=re_xxx
EMAIL_FROM=noreply@contentflow.dev
EMAIL_FROM_NAME=ContentFlow
EMAIL_REPLY_TO=support@contentflow.dev
EMAIL_DASHBOARD_URL=https://contentflow.dev/dashboard
EMAIL_DOCS_URL=https://contentflow.dev/docs
EMAIL_UNSUBSCRIBE_BASE=https://contentflow.dev/unsubscribe
```

---

## 작업 8: 테스트

- `tests/test_email_service.py` — Resend는 mock
- `tests/test_email_templates.py` — 템플릿 렌더링
- `tests/test_onboarding.py` — 온보딩 플로우
- `tests/test_email_verify.py` — 이메일 인증
- `tests/test_notification_prefs.py` — 알림 설정

---

## 완료 기준

- [ ] Resend SDK 통합
- [ ] 10개 이메일 템플릿 (HTML + 텍스트)
- [ ] 이벤트별 자동 발송 연결
- [ ] 온보딩 API
- [ ] 이메일 인증 플로우
- [ ] 알림 설정 관리
- [ ] email_logs 테이블
- [ ] 테스트 추가
- [ ] ruff + pytest 통과

---

## 참고

Resend 무료 플랜: 월 3,000 통, 100/일.
프로덕션 사용량 늘면 유료 플랜 ($20/월부터) 또는 SendGrid로 마이그레이션.
워크스페이스 브랜딩과 통합되어야 white-label 가치가 살아난다.
