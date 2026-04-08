# TASK: 보안 감사 + 하드닝

> 담당: 코드3
> 우선순위: P0 (프로덕션 출시 전 필수)

---

## 배경

ContentFlow는 SaaS 제품으로 가는 중이다. 결제, OAuth 토큰, API Key, 사용자 데이터를 다루는 시스템이라 **보안 취약점이 있으면 회사가 망한다.**

이번 작업은 기존 코드의 보안 취약점을 찾아서 막고, 프로덕션 배포 전 보안 기준선을 세우는 것이다.

---

## 작업 1: 보안 감사 (Security Audit)

### 파일: `docs/SECURITY_AUDIT.md`

전체 코드베이스를 검토해서 다음 항목을 체크하고 발견된 이슈를 리포트로 작성한다.

### 1.1 인증/인가 (Authentication & Authorization)

- [ ] 모든 엔드포인트가 인증을 요구하는가? (`Depends(get_current_user)` 누락 체크)
- [ ] 사용자가 자기 데이터만 접근할 수 있는가? (IDOR 취약점 체크)
  - posts, videos, accounts, webhooks, api_keys 등 모든 리소스
- [ ] Admin 엔드포인트는 admin 권한을 제대로 검증하는가?
- [ ] API Key 비교 시 timing-safe 비교 사용? (`hmac.compare_digest`)
- [ ] JWT 토큰 검증 시 알고리즘 명시? (`alg=none` 공격 방어)

### 1.2 OAuth 토큰 보안

- [ ] 토큰이 평문으로 저장되지 않는가? (AES-256 암호화 확인)
- [ ] 암호화 키가 환경변수로 관리되는가?
- [ ] 키 회전 가능한 구조인가?
- [ ] 로그에 토큰이 노출되지 않는가?
- [ ] 에러 메시지에 토큰이 포함되지 않는가?

### 1.3 API Key 관리

- [ ] DB에 평문 키가 아닌 해시만 저장되는가?
- [ ] bcrypt cost factor가 적절한가? (12 이상)
- [ ] 키 발급 시 secure random 사용? (`secrets.token_urlsafe`)
- [ ] 키 prefix만 저장 (식별용), 본문은 한 번만 노출?

### 1.4 입력 검증 (Input Validation)

- [ ] 모든 Pydantic 모델에 max_length 설정?
- [ ] URL 입력 시 스킴 검증? (http/https만 허용)
- [ ] Webhook URL이 내부 IP를 가리키지 않는가? (SSRF 방어)
- [ ] 파일 업로드 시 MIME type + 크기 검증?
- [ ] SQL injection 가능성? (Supabase 클라이언트는 안전하지만 raw query 체크)

### 1.5 출력 인코딩 (Output Encoding)

- [ ] 에러 메시지에 사용자 입력이 그대로 반사되지 않는가?
- [ ] 로그에 PII (개인정보)가 마스킹되는가?
- [ ] API 응답에 민감 필드 (password_hash, secret) 노출 안 됨?

### 1.6 Rate Limiting & DDoS

- [ ] 모든 엔드포인트에 rate limit 적용?
- [ ] 로그인/회원가입 같은 민감 엔드포인트는 더 엄격한 제한?
- [ ] IP 기반 차단 가능?
- [ ] 큰 페이로드 거부? (요청 본문 크기 제한)

### 1.7 Webhook 보안

- [ ] HMAC 서명 검증 의무화?
- [ ] Replay attack 방어 (timestamp 검증)?
- [ ] 웹훅 URL이 사용자별로 격리?
- [ ] 외부 콜백 시 SSRF 방어?

### 1.8 Stripe 보안

- [ ] Webhook 서명 검증 (`stripe.Webhook.construct_event`)?
- [ ] 결제 금액을 클라이언트가 조작 못 하는가? (서버에서만 결정)
- [ ] customer_id를 사용자가 변경 못 하는가?

### 1.9 환경 변수 & 시크릿

- [ ] `.env`가 `.gitignore`에 있는가?
- [ ] 코드에 하드코딩된 키 없는가?
- [ ] `.env.example`에 실제 값 없는가?
- [ ] CI/CD에서 시크릿이 로그에 출력되지 않는가?

### 1.10 의존성 보안

- [ ] `pip-audit` 또는 `safety` 실행 결과
- [ ] 알려진 CVE가 있는 패키지?
- [ ] 의존성 최신 버전 여부

---

## 작업 2: 발견된 이슈 수정

작업 1에서 발견한 모든 이슈를 우선순위별로 수정한다.

- **Critical**: 즉시 수정 (인증 우회, 토큰 노출, SQL injection)
- **High**: 24시간 내 수정 (IDOR, SSRF, 약한 암호화)
- **Medium**: 1주일 내 수정 (rate limit 부족, 로그 PII)
- **Low**: 백로그 (의존성 업데이트, 헤더 보강)

수정 내역은 `docs/SECURITY_AUDIT.md`에 기록.

---

## 작업 3: 보안 미들웨어 강화

### 파일: `app/core/security_middleware.py`

다음 보안 헤더 자동 추가:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

### 파일: `app/core/request_validator.py`

- 요청 본문 크기 제한 (기본 10MB, 영상 업로드는 100MB)
- 비정상 헤더 감지 (User-Agent 누락, suspicious patterns)
- 알려진 봇/스캐너 차단

---

## 작업 4: SSRF 방어

### 파일: `app/core/url_validator.py`

웹훅 URL, 미디어 URL 검증:

```python
def validate_external_url(url: str) -> bool:
    """
    외부 URL 검증.
    - http/https만 허용
    - 내부 IP 차단 (10.x, 172.16-31, 192.168, 127.x, ::1, fe80)
    - localhost, *.local 차단
    - DNS resolve 후 재검증 (DNS rebinding 방어)
    """
```

webhook 등록, posts media_urls, video URL 등 외부 URL을 받는 모든 곳에 적용.

---

## 작업 5: 시크릿 스캔

### 파일: `scripts/secret_scan.py`

- 코드베이스에서 시크릿 패턴 검색
  - API 키 패턴: `sk_live_`, `sk_test_`, `cf_live_`, `cf_test_`
  - AWS: `AKIA[0-9A-Z]{16}`
  - Google: `AIza[0-9A-Za-z\-_]{35}`
  - JWT: `eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.`
  - Private keys: `-----BEGIN PRIVATE KEY-----`
- Git history도 스캔
- 발견되면 fail (CI 통합)

`.github/workflows/security.yml`에 추가:
- pip-audit
- secret_scan
- 매일 1회 자동 실행

---

## 작업 6: 권한 검증 통합 테스트

### 파일: `tests/test_security/`

- `test_idor.py` — 다른 사용자 리소스 접근 시도
  - 모든 리소스 (posts, videos, accounts, webhooks, api_keys, workspaces)
  - 다른 사용자 ID로 GET/PATCH/DELETE 시도 → 403/404
- `test_auth_bypass.py` — 인증 우회 시도
  - 키 없이 호출
  - 잘못된 키
  - 만료된 키
  - 비활성화된 키
- `test_admin_isolation.py` — 일반 키로 admin 엔드포인트 접근 시도
- `test_ssrf.py` — SSRF 공격 시뮬레이션
  - 내부 IP, localhost, file:// 등
- `test_input_validation.py` — 큰 페이로드, 비정상 입력

---

## 작업 7: 침투 테스트 시나리오

### 파일: `docs/PENTEST_SCENARIOS.md`

화이트박스 침투 테스트 시나리오 작성:

1. **계정 탈취 시나리오** — API Key 추측, brute force, leak 시뮬레이션
2. **데이터 유출 시나리오** — IDOR, SQL injection, 에러 메시지 정보 누출
3. **결제 우회 시나리오** — Stripe webhook 위조, 금액 조작, 무료 사용
4. **OAuth 토큰 탈취** — XSS, CSRF, 토큰 재사용
5. **DoS 시나리오** — Rate limit 우회, resource exhaustion
6. **권한 상승** — 일반 사용자 → admin

각 시나리오에 대한 방어 매커니즘 설명 + 테스트 코드.

---

## 작업 8: SECURITY.md 업데이트

기존 `docs/SECURITY.md`를 다음 내용으로 보강:

- Threat Model
- Security Architecture Diagram
- 보안 책임 모델 (사용자 vs ContentFlow)
- 사고 대응 프로세스 (Incident Response)
- 취약점 신고 채널 (security@contentflow.dev)
- Bug Bounty 정책 (선택)
- Compliance (GDPR, SOC 2 준비 사항)

---

## 완료 기준

- [ ] `docs/SECURITY_AUDIT.md` 전체 감사 결과
- [ ] 발견된 Critical/High 이슈 모두 수정
- [ ] `app/core/security_middleware.py` 보안 헤더
- [ ] `app/core/url_validator.py` SSRF 방어
- [ ] `scripts/secret_scan.py` 시크릿 스캔
- [ ] `.github/workflows/security.yml` 자동 보안 검사
- [ ] `tests/test_security/` 보안 테스트 (최소 30개)
- [ ] `docs/PENTEST_SCENARIOS.md` 침투 테스트 시나리오
- [ ] `docs/SECURITY.md` 보강
- [ ] ruff + pytest 통과
- [ ] 모든 보안 테스트 통과

---

## 중요

이건 **새 기능 추가가 아니다.** 기존 코드의 보안 취약점을 찾고 막는 작업이다.

발견되는 이슈가 많을수록 좋다. 그게 이 작업의 가치다. 이슈를 못 찾았다고 "다 안전합니다"라고 보고하지 마라. 그건 게으른 거다. 적극적으로 공격자 관점에서 코드를 읽어라.

특히 다음 영역을 집중 검토:
1. `app/api/v1/` 모든 엔드포인트의 권한 체크
2. `app/oauth/` 토큰 처리
3. `app/api/v1/billing.py` + `app/api/webhooks/stripe.py` 결제
4. `app/core/auth.py` 인증
5. `app/core/webhook_dispatcher.py` 외부 호출
