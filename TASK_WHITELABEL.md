# TASK: White-Label + Multi-Tenant 기능

> 담당: 코덱1
> 우선순위: P1

---

## 배경

Zernio의 핵심 차별점 중 하나는 white-label이다. SaaS 빌더들이 ContentFlow를 자기 제품에 끼워 넣을 때 ContentFlow 브랜딩이 노출되지 않게 하는 기능이다.

이 기능이 있어야 ContentFlow가 진짜 "API as a Service"로 팔린다.

---

## 작업 1: Workspace 모델

### DB 스키마 추가 (`app/models/schemas.py`)

신규 테이블 `workspaces`:
- id (UUID)
- owner_id (FK users)
- name (TEXT)
- slug (TEXT, unique) — 서브도메인용
- branding (JSONB) — logo_url, primary_color, font, support_email
- custom_domain (TEXT, nullable)
- white_label_enabled (BOOLEAN)
- created_at

기존 테이블 확장:
- users 테이블에 `default_workspace_id` 추가
- api_keys 테이블에 `workspace_id` 추가
- social_accounts 테이블에 `workspace_id` 추가
- posts 테이블에 `workspace_id` 추가

같은 user가 여러 workspace를 가질 수 있고, API key는 workspace 단위로 발급된다.

---

## 작업 2: Workspace API

### 파일: `app/api/v1/workspaces.py`

- `POST /api/v1/workspaces` — workspace 생성
- `GET /api/v1/workspaces` — 내 workspace 목록
- `GET /api/v1/workspaces/{id}` — 상세
- `PATCH /api/v1/workspaces/{id}` — 정보 수정
- `DELETE /api/v1/workspaces/{id}` — 삭제 (소프트 삭제)
- `POST /api/v1/workspaces/{id}/branding` — 브랜딩 설정 (logo/color/font)
- `POST /api/v1/workspaces/{id}/domain` — 커스텀 도메인 설정

### Workspace switching
- 모든 API call에 `X-Workspace-Id` 헤더 옵션
- 미지정 시 default_workspace 사용
- API key는 workspace에 종속

---

## 작업 3: White-Label Webhook + 이메일 템플릿

### 파일: `app/core/branding.py`

- `get_workspace_branding(workspace_id)` → branding dict
- `render_email_template(template, workspace, context)` — 이메일 템플릿 렌더링
- `render_webhook_payload(event, workspace, data)` — 웹훅에 workspace 브랜딩 적용

### 적용 위치
- 웹훅 발송 시 `from_brand` 필드 추가 (workspace.name)
- 이메일 알림 시 logo/color/support_email 사용
- API 에러 응답에 `documentation_url` 필드 (workspace 커스텀 가능)

---

## 작업 4: Custom Domain 지원

### 파일: `app/middleware/custom_domain.py`

- 요청 Host 헤더 → workspace 매핑
- 커스텀 도메인 (`api.customer.com`) → workspace_id 자동 식별
- DNS verification (TXT 레코드 체크)

### 파일: `app/api/v1/domains.py`
- `POST /api/v1/workspaces/{id}/domain/verify` — DNS 검증
- 검증 토큰 생성 + TXT 레코드 안내

---

## 작업 5: Workspace 단위 사용량/과금

### 변경 사항
- `app/core/billing.py`에 workspace 단위 사용량 추적
- usage 테이블에 workspace_id 추가
- API 호출 시 workspace_id 기준으로 카운팅
- 워크스페이스별 한도는 user의 plan을 상속하되, 향후 분리 가능

---

## 작업 6: Workspace Member (Team)

### DB 추가
신규 테이블 `workspace_members`:
- id, workspace_id, user_id, role (owner/admin/editor/viewer), invited_by, joined_at

### 파일: `app/api/v1/members.py`
- `POST /api/v1/workspaces/{id}/members/invite` — 초대
- `GET /api/v1/workspaces/{id}/members` — 멤버 목록
- `PATCH /api/v1/workspaces/{id}/members/{user_id}` — 권한 변경
- `DELETE /api/v1/workspaces/{id}/members/{user_id}` — 추방

권한별 가능한 작업:
- owner: 모든 권한
- admin: 멤버 관리 제외 모든 권한
- editor: 콘텐츠 생성/배포만
- viewer: 읽기 전용

---

## 작업 7: 테스트

- `tests/test_workspaces.py`
- `tests/test_workspace_members.py`
- `tests/test_branding.py`
- `tests/test_custom_domain.py`

---

## 완료 기준

- [ ] workspaces, workspace_members 테이블
- [ ] 기존 테이블에 workspace_id 추가
- [ ] Workspace API
- [ ] Branding 시스템
- [ ] Custom domain 미들웨어
- [ ] 멤버 관리 + 권한
- [ ] workspace 단위 사용량
- [ ] 테스트 추가
- [ ] ruff + pytest 통과

---

## 의미

이거 끝나면 ContentFlow가 진짜로 "API 인프라"가 된다. Buffer/Hootsuite 같은 GUI 제품이 아니라, 다른 SaaS 빌더들이 자기 제품에 통합해서 쓰는 인프라.

Zernio가 자랑하는 white-label을 같은 수준으로 갖추는 거다.
