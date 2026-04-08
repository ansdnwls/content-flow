# TASK: Load Testing + Admin Panel

> 담당: 코덱1
> 우선순위: P1

---

## 작업 1: Load Testing

### 파일: `tests/load/locustfile.py`

Locust 기반 부하 테스트 시나리오:

- **시나리오 1**: Posts API 부하
  - POST /api/v1/posts (3개 플랫폼) — weight 10
  - GET /api/v1/posts/{id} — weight 5
  - GET /api/v1/posts — weight 3

- **시나리오 2**: Bulk + Bombs
  - POST /api/v1/posts/bulk (10개씩) — weight 2
  - POST /api/v1/bombs — weight 1

- **시나리오 3**: Read-heavy
  - GET /api/v1/analytics — weight 5
  - GET /api/v1/usage — weight 5
  - GET /api/v1/trending — weight 3

### 파일: `scripts/run_load_test.sh`
- 100/500/1000 동시 사용자 시나리오 자동 실행
- 결과를 `reports/load/` 에 저장

### 파일: `docs/PERFORMANCE.md`
- 부하 테스트 결과 리포트
- 병목 분석
- 개선 제안

---

## 작업 2: Admin Panel API

### 파일: `app/api/v1/admin.py`

관리자 전용 엔드포인트 (별도 admin API key 필요):

- `GET /api/v1/admin/users` — 전체 사용자 목록
- `GET /api/v1/admin/users/{id}` — 사용자 상세 (사용량, 결제 상태)
- `POST /api/v1/admin/users/{id}/plan` — 플랜 변경
- `POST /api/v1/admin/users/{id}/suspend` — 계정 정지
- `GET /api/v1/admin/stats` — 전체 시스템 통계
  - 총 사용자, 활성 사용자, 총 포스트, 총 영상, 수익 추정
- `GET /api/v1/admin/jobs` — Celery 작업 상태 모니터링
- `GET /api/v1/admin/health` — 전체 시스템 헬스 체크

### 파일: `app/core/admin_auth.py`
- 관리자 권한 체크 미들웨어
- `X-Admin-Key` 헤더로 검증
- 일반 API key와 분리

---

## 작업 3: Database Migration Tooling

### 파일: `alembic.ini` + `migrations/`

Alembic 설정으로 DB 스키마 마이그레이션 자동화:
- `alembic init migrations`
- 기존 `infra/supabase/01_schema.sql`을 기반으로 초기 마이그레이션 생성
- 이후 모델 변경 시 `alembic revision --autogenerate` 사용 가능

### 파일: `scripts/migrate.sh`
- 운영 환경 마이그레이션 실행 스크립트
- 백업 → 마이그레이션 → 검증 순서

---

## 완료 기준

- [ ] Locust 부하 테스트 시나리오 작성
- [ ] 100/500/1000 사용자 부하 결과 리포트
- [ ] Admin Panel API 엔드포인트 구현
- [ ] Admin 전용 인증 미들웨어
- [ ] Alembic 마이그레이션 설정
- [ ] ruff + pytest 통과
