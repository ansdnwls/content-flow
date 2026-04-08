# Smoke Test

`scripts/smoke_test.py`는 로컬 `docker compose` 환경이 실제로 올라와 있는지 빠르게 확인하는 배포 smoke runner다. 기본 흐름은 `/health/live`, `/health/ready`, DB/Redis readiness, API key 발급/저장 확인, workspace 생성, post dry-run, webhook 등록 및 전송 검증 순서로 진행된다.

## Local Run

1. `.env`에 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`를 채운다.
2. 로컬에서 스크립트를 직접 DB에 붙여야 하므로 host 기준으로 접근 가능한 Redis URL을 쓴다.
3. `docker compose up -d --build`
4. `python scripts/smoke_test.py`

호스트에서 compose까지 같이 띄우려면 아래처럼 실행한다.

```bash
python scripts/smoke_test.py --start-compose
```

기본 리포트는 `scripts/smoke_test_results.generated.md`에 생성된다.

## CI

`.github/workflows/smoke.yml`은 PR마다 다음 순서로 실행된다.

1. Python 의존성 설치
2. GitHub Secrets 기반 `.env` 생성
3. `docker compose up -d --build`
4. `python scripts/smoke_test.py`
5. smoke report와 compose 로그 업로드

필수 secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`

워크플로 실패가 실제 merge 차단으로 이어지려면 GitHub branch protection에서 `Smoke` job을 required status check로 지정해야 한다.

## Notes

- 현재 코드베이스에는 webhook 생성용 공개 API가 없어서 smoke runner는 DB에 webhook row를 bootstrap한 뒤 `dispatch_event()`로 실제 전송까지 검증한다.
- `posts` smoke는 publish가 아니라 `dry_run=true`만 호출한다. 외부 플랫폼 자격증명이 없어도 200 응답과 wiring 확인이 가능하다.
- readiness는 Celery worker까지 포함한다. `docker compose`에서 `worker`가 안 뜨면 `/health/ready`가 실패한다.

## Extension

- 새로운 smoke 단계를 추가할 때는 `scripts/smoke_test.py`에 `StepResult`를 반환하는 함수 하나를 만들고 `run_smoke()`에 연결한다.
- Markdown 리포트 형식을 바꾸려면 `scripts/smoke_test_results.md` 템플릿의 placeholder만 유지하면 된다.
- 특정 vertical smoke를 붙일 때는 공통 smoke 이후 별도 `vertical` 단계로 추가하는 편이 실패 원인 분리가 쉽다.
