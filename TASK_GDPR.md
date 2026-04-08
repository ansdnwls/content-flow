# TASK: GDPR + 컴플라이언스

> 담당: 코드3
> 우선순위: P1 (유럽/미국 고객 받기 전 필수)

---

## 배경

ContentFlow는 SaaS로서 사용자 데이터(이메일, 소셜 토큰, 결제 정보)를 다룬다. 유럽 사용자가 한 명이라도 가입하는 순간 GDPR 적용 대상이 되고, 미국 캘리포니아 사용자라면 CCPA도 적용된다.

**컴플라이언스 미준수는 회사가 망하는 길이다.** 지금 미리 준비하자.

또한 SOC 2 Type II 준비도 시작한다 (엔터프라이즈 고객 영업의 필수 조건).

---

## 작업 1: 데이터 권리 API (GDPR Art. 15-21)

### 파일: `app/api/v1/privacy.py`

GDPR이 보장하는 사용자 권리를 API로 구현:

### 1.1 정보 접근권 (Right to Access, Art. 15)
```
GET /api/v1/privacy/me
```
- 사용자가 자기 데이터 전체 조회
- 응답: 개인정보, 사용 내역, 연결 계정, 결제 이력 요약

### 1.2 데이터 이동권 (Right to Data Portability, Art. 20)
```
POST /api/v1/privacy/export
```
- 사용자 데이터 전체를 JSON 또는 ZIP으로 내보내기
- 비동기 처리 (Celery)
- 완료 시 다운로드 링크 이메일 발송 (24시간 유효)
- 포함 데이터:
  - 프로필
  - 모든 posts, videos
  - 연결된 social_accounts (토큰 제외, 메타데이터만)
  - 분석 데이터
  - 결제 이력
  - audit_logs
  - 웹훅 설정
- 형식: 머신 리더블 JSON + 사람 읽기 쉬운 HTML 요약

### 1.3 정정권 (Right to Rectification, Art. 16)
```
PATCH /api/v1/privacy/me
```
- 프로필 수정 엔드포인트 (이미 settings에 있을 수 있음)

### 1.4 삭제권 (Right to Erasure, Art. 17)
```
DELETE /api/v1/privacy/me
```
- 계정 완전 삭제 요청
- 14일 grace period (실수 방지)
- 14일 동안:
  - 계정 비활성화 (로그인 불가)
  - 모든 API key 비활성화
  - 진행 중인 구독 취소 (Stripe)
- 14일 후 자동 삭제 (Celery Beat):
  - 모든 개인 데이터 삭제
  - 익명화: posts, audit_logs는 user_id를 NULL로 (분석용 통계 보존)
  - social_accounts는 토큰 즉시 폐기 후 소프트 삭제
- 삭제 완료 시 confirmation 이메일

### 1.5 처리 제한권 (Right to Restriction, Art. 18)
```
POST /api/v1/privacy/restrict
```
- 처리 일시 정지 요청
- 데이터는 보존하지만 모든 워커가 무시

### 1.6 이의 제기권 (Right to Object, Art. 21)
```
POST /api/v1/privacy/object
```
- 마케팅 이메일, 분석 등에 대한 이의 제기
- notification preferences와 통합

---

## 작업 2: 동의 관리 (Consent Management)

### 파일: `app/api/v1/consent.py`

GDPR Art. 7에 따라 동의는 명시적이고 추적 가능해야 한다.

### DB 스키마 (`app/models/schemas.py`)

신규 테이블 `consents`:
- id, user_id, purpose, granted, granted_at, revoked_at, ip, user_agent, version

purposes:
- `essential` — 서비스 제공 (필수, 동의 불가)
- `analytics` — 사용 패턴 분석
- `marketing` — 마케팅 이메일
- `third_party_sharing` — 외부 서비스 데이터 공유 (Stripe, Resend 등)
- `cookies_functional` — 기능 쿠키
- `cookies_analytics` — 분석 쿠키

### 엔드포인트
- `GET /api/v1/consent` — 현재 동의 상태
- `POST /api/v1/consent/grant` — 특정 목적 동의
- `POST /api/v1/consent/revoke` — 동의 철회
- `GET /api/v1/consent/history` — 동의 변경 이력 (감사 추적)

가입 시 essential은 자동 동의, 나머지는 명시적 opt-in 필수.

---

## 작업 3: 데이터 보존 정책 (Data Retention)

### 파일: `app/services/retention_service.py`

각 데이터 유형별 보존 기간 정의:

| 데이터 | 보존 기간 | 삭제 방법 |
|--------|---------|----------|
| Posts | 무기한 (사용자가 삭제 전까지) | 사용자 액션 |
| Audit logs | 1년 | 자동 삭제 |
| Email logs | 90일 | 자동 삭제 |
| Webhook deliveries | 30일 | 자동 삭제 |
| Sessions | 7일 | 자동 삭제 |
| Deleted users | 14일 후 영구 삭제 | grace period |
| Payment records | 7년 (세무 의무) | 자동 (단, 익명화) |
| Analytics snapshots | 2년 | 자동 |

### Celery Beat task
- 매일 새벽 3시 retention_worker 실행
- 보존 기간 지난 데이터 자동 삭제
- 삭제 결과를 audit_logs에 기록

---

## 작업 4: PII 분류 및 암호화

### 파일: `app/core/pii_classifier.py`

PII (개인식별정보) 자동 분류:

```python
PII_FIELDS = {
    "email": "high",
    "name": "medium",
    "ip_address": "medium",
    "user_agent": "low",
    "stripe_customer_id": "medium",
    "phone": "high",
    "social_account_username": "medium",
}
```

- 로그 출력 시 자동 마스킹
- 에러 메시지에서 자동 제거
- API 응답에서 admin이 아니면 마스킹

### 저장 시 암호화
- email: 검색 가능해야 하므로 hash + plaintext 둘 다 저장 (양방향 암호화)
- phone: AES-256 암호화
- name: AES-256 암호화 (선택)
- 기존 OAuth 토큰은 이미 암호화됨

---

## 작업 5: 데이터 처리 약정서 (DPA) 자동화

### 파일: `app/api/v1/legal.py`

엔터프라이즈 고객은 DPA (Data Processing Agreement) 서명을 요구한다.

- `GET /api/v1/legal/dpa` — DPA 현재 버전 조회
- `POST /api/v1/legal/dpa/sign` — DPA 서명 (회사명, 서명자, IP 기록)
- `GET /api/v1/legal/dpa/signed` — 서명한 DPA 다운로드 (PDF)
- `GET /api/v1/legal/sub-processors` — 하위 처리자 목록 (Stripe, Resend, Supabase 등)

### DB
신규 테이블 `dpa_signatures`:
- id, user_id, dpa_version, signer_name, signer_email, company, signed_at, ip, pdf_url

---

## 작업 6: 데이터 침해 알림 시스템

### 파일: `app/services/breach_notification.py`

GDPR Art. 33-34: 데이터 침해 발생 시 72시간 내 감독 기관 통보, 영향받은 사용자에게 알림.

- `report_breach(severity, affected_users, description)` — 침해 신고
- 자동:
  - 영향받은 사용자에게 이메일 알림 (breach_notification.html 템플릿)
  - 감독 기관 통보 템플릿 자동 생성
  - 내부 incident response 체크리스트
- 모든 침해 사건은 `data_breaches` 테이블에 기록

---

## 작업 7: 쿠키 동의 (Cookie Consent)

### 파일: `dashboard/components/cookie-banner.tsx`

대시보드와 랜딩페이지 양쪽에 적용:

- 첫 방문 시 쿠키 배너
- Essential / Functional / Analytics 카테고리별 동의
- "Reject all" 버튼 (GDPR 필수: accept만큼 거부도 쉬워야 함)
- 동의 정보를 백엔드 consent API로 전송
- 1년 후 재동의 요청

---

## 작업 8: Privacy Policy + Cookie Policy 페이지

### 파일: `landing/app/legal/`

- `privacy/page.tsx` — 개인정보 처리방침 (한국어 + 영어)
- `cookies/page.tsx` — 쿠키 정책
- `terms/page.tsx` — 이용약관 (이미 있을 수 있음)
- `dpa/page.tsx` — DPA 템플릿
- `subprocessors/page.tsx` — 하위 처리자 목록

내용은 GDPR/CCPA 기본 템플릿 기반으로 작성. 실제 법무 검토는 사장님이 별도로 받아야 함.

---

## 작업 9: SOC 2 준비 사항

### 파일: `docs/SOC2_READINESS.md`

SOC 2 Type II 준비 체크리스트:

### Security (이미 SECURITY.md로 정리됨, 보강)
- [x] Access controls (API Key, OAuth)
- [x] Encryption at rest (DB, tokens)
- [x] Encryption in transit (HTTPS only)
- [x] Vulnerability management (security CI)
- [x] Incident response plan

### Availability
- [ ] Uptime monitoring (Sentry, statuspage)
- [ ] Disaster recovery plan
- [ ] Backup and restore procedures
- [ ] SLA 정의 (99.9%)

### Processing Integrity
- [x] Input validation
- [x] Audit logs
- [ ] Change management process

### Confidentiality
- [x] Data classification (PII)
- [x] Need-to-know access (RLS)
- [ ] NDA with employees/contractors

### Privacy
- [x] GDPR compliance (이 작업으로 완성)
- [x] Consent management
- [x] Data retention
- [x] User rights API

각 항목에 대해 현재 상태와 부족한 부분 명시.

---

## 작업 10: 컴플라이언스 대시보드 (admin)

### 파일: `app/api/v1/admin/compliance.py`

관리자가 컴플라이언스 상태를 한눈에 볼 수 있는 엔드포인트:

- `GET /api/v1/admin/compliance/dashboard`
  - 총 사용자 / 동의한 사용자 비율
  - 데이터 삭제 요청 대기 중 / 처리됨
  - 이번 달 데이터 내보내기 요청 수
  - 최근 침해 사건
  - DPA 서명한 엔터프라이즈 고객 수
- `GET /api/v1/admin/compliance/pending-deletions`
- `GET /api/v1/admin/compliance/data-requests`

---

## 작업 11: 테스트

- `tests/test_privacy.py` — 데이터 권리 API
- `tests/test_consent.py` — 동의 관리
- `tests/test_retention.py` — 데이터 보존
- `tests/test_breach.py` — 침해 알림
- `tests/test_pii_masking.py` — PII 마스킹

---

## 완료 기준

- [ ] 데이터 권리 API (access, export, delete, rectify, restrict, object)
- [ ] 동의 관리 시스템
- [ ] 데이터 보존 worker
- [ ] PII 분류 및 자동 마스킹
- [ ] DPA 서명 시스템
- [ ] 데이터 침해 알림 시스템
- [ ] 쿠키 배너 (랜딩 + 대시보드)
- [ ] Privacy/Cookie/Terms/DPA 페이지
- [ ] SOC 2 준비 문서
- [ ] 컴플라이언스 admin 대시보드
- [ ] 테스트 추가
- [ ] ruff + pytest 통과

---

## 의미

이 작업이 끝나면 ContentFlow는:

1. **유럽 고객을 받아도 안전** (GDPR 완비)
2. **미국 캘리포니아 고객도 OK** (CCPA 호환)
3. **엔터프라이즈 영업 가능** (DPA + SOC 2 준비)
4. **법적 리스크 최소화** (데이터 보존, 침해 대응)

이게 있어야 큰 회사들이 ContentFlow를 도입할 수 있다. 개인 크리에이터 대상이라면 필요 없지만, **B2B로 가면 컴플라이언스가 곧 매출**이다.
