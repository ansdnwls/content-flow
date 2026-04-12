# ContentFlow Backlog

> 아이디어 저장소. 구현 전에 반드시 우선순위 평가 후 현재 스프린트에 포함된 것만 작업합니다. 이 파일은 사장님(JIN)과 Claude의 약속:
>
> 1. 새 아이디어 나오면 무조건 여기 먼저 추가
> 2. 즉흥 구현 금지
> 3. 한 번에 하나만 집중

---

## 🎯 Current Sprint

**스프린트 목표**: (아직 결정 안 됨 - 다음 세션에서 B01\~B07 중 선택)

**선택 기준**:

- 사장님이 매일 쓸 것 같은 기능 우선
- 첫 5명 유저가 돈 낼 기능 우선
- 외부 의존성 적은 것 우선
- 기존 코드 재사용 가능한 것 우선

---

## 📋 Backlog Items

### B01. yt-factory 연동 (OSMU 엔진 연결)

**설명**: newVideoGen/yt-factory python과 ContentFlow webhook 연결하여 영상 생성 → 자동 배포 파이프라인 구축

**상세**:

- ContentFlow 쪽 `_run_yt_factory()` 이미 구현됨
- yt-factory 측에 FastAPI 래퍼 `/api/v1/pipelines/run`, `/api/v1/pipelines/{id}` 추가 필요
- 또는 subprocess 직접 호출 / Redis 큐 방식

**난이도**: 중 **재사용**: `app/workers/video_worker.py::_run_yt_factory()` 존재 **예상 시간**: 2\~4시간 **외부 의존성**: 없음 **전제 조건**: 없음 **우선순위 메모**: OSMU 전략의 핵심. 이거 없으면 ContentFlow 혼자로는 반쪽짜리.

---

### B02. 한국 블로그 다채널 발행

**설명**: 유튜브 자막 → Claude 블로그 변환 → Naver 블로그/Tistory 자동 발행

**상세**:

- `content_transformer.py`, `naver_blog.py`, `tistory.py` 어댑터 존재
- OAuth 실제 검증 필요
- Tistory는 API 개편 후 제한 많음 (확인 필요)
- Naver 블로그는 공식 API 아닌 자동화 방식 고려

**난이도**: 중 **재사용**: 어댑터 코드 존재 **예상 시간**: 4\~8시간 (OAuth 디버깅 포함) **외부 의존성**: Naver Developers OAuth, Tistory API **전제 조건**: B07 (자막 추출) 권장 **우선순위 메모**: 한국 특화 포인트. 경쟁 서비스가 잘 못하는 영역. 차별화 가치 높음.

---

### B03. Instagram/TikTok/Threads 쇼츠 배포

**설명**: 쇼츠 mp4 → 각 플랫폼에 맞는 캡션 AI 생성 → 자동 업로드

**상세**:

- 21개 어댑터 중 Instagram, TikTok, Threads 존재 (코드만)
- OAuth 실제 검증 X
- 각 플랫폼 캡션/해시태그 스타일이 다름 → Claude로 재작성
- Instagram 먼저, TikTok은 한국 승인 까다로움

**난이도**: 중\~상 **재사용**: 어댑터 코드, OAuth proxy 일부 **예상 시간**: 플랫폼당 4\~8시간 **외부 의존성**: Meta Developers (Facebook 앱 심사), TikTok for Developers **전제 조건**: B01 (yt-factory 연동) 권장 **우선순위 메모**: Instagram 먼저. TikTok은 한국 승인 대기 시간 고려.

---

### B04. 카드뉴스 자동 생성

**설명**: 유튜브 자막 → Claude 10장 구성 → HTML 템플릿 → PNG → Instagram 캐러셀

**상세**:

- 입력: 유튜브 롱폼 URL
- 스타일: 인포그래픽 (차트/아이콘) 또는 사진 배경 + 텍스트
- 타겟: 사장님 본인 Instagram 계정
- "자세한 내용은 유튜브에서" CTA로 트래픽 루프
- 이미지 생성: Playwright HTML→PNG 방식 권장

**난이도**: 하\~중 **재사용**: Claude 연동 기존 사용 **예상 시간**: 4\~6시간 (MVP) **외부 의존성**: Playwright, Cloudinary (또는 S3) **전제 조건**: B07 (자막 추출) 필요 **우선순위 메모**: 영상과 독립적이라 빨리 만들 수 있음. 인스타 → 유튜브 트래픽 루프가 매력적.

---

### B05. 해외 영상 벤치마킹 도구

**설명**: 해외 유튜브 URL → 자막 추출 → Claude 구조 분석 → 한국어 각색 대본 + 촬영 가이드

**상세**:

- 저작권 안전 (아이디어는 저작권 없음, 표현만 저작권)
- 결과: 주제, 훅, 본문 구조, 성공 요인, 한국어 각색 대본, 제목 5개, 썸네일 컨셉 3개
- 영상 다운로드/재업로드 X (절대 금지)
- 사장님의 콘텐츠 기획 도구로 활용

**난이도**: 하 **재사용**: Claude 연동 기존 사용 **예상 시간**: 2\~4시간 **외부 의존성**: yt-dlp (자막 추출) **전제 조건**: B07 (자막 추출) **우선순위 메모**: 가장 빨리 만들 수 있고 즉시 사용 가능.

---

### B06. 쿠팡 파트너스 쇼핑 쇼츠

**설명**: 쿠팡 상품 → AI 리뷰 대본 → TTS → 스톡 영상 합성 → 쇼츠 업로드 (파트너스 링크)

**상세**:

- 수익 모델: 쿠팡 파트너스 수수료 (3\~10%)
- 저작권 안전 (상품 설명은 공개 정보)
- 영상 처리 필요 → yt-factory 연동 선행
- YouTube AI 콘텐츠 정책 주의 필요

**난이도**: 상 **재사용**: 적음 **예상 시간**: 1\~2주 **외부 의존성**: 쿠팡 파트너스 API, ElevenLabs TTS, Pexels/Pixabay, yt-factory **전제 조건**: B01 (yt-factory 연동) 필수 **우선순위 메모**: 수익 잠재력 있으나 복잡도 높음. 다른 기능 검증 후 고려.

---

### B07. YouTube 자막 자동 추출

**설명**: yt-dlp 또는 YouTube Caption API로 긴 영상 자막 자동 추출

**상세**:

- 현재: 수동 transcript 입력만 가능 (2026-04-11 테스트)
- B02, B04, B05 모두의 전제 조건
- yt-dlp가 가장 안정적 (다국어, 자동 생성 자막 지원)
- 또는 YouTube Caption API (공식이지만 제한 있음)

**난이도**: 하 **재사용**: 없음 (신규) **예상 시간**: 1\~2시간 **외부 의존성**: yt-dlp (pip install) **전제 조건**: 없음 **우선순위 메모**: **최우선 후보**. 많은 기능의 전제 조건.

---

### ~~B08. Claude JSON 응답 파싱 통일~~ ✅ 완료 (2026-04-11)

**설명**: Claude API 응답이 마크다운 코드펜스로 감싸질 때 JSONDecodeError 발생하는 문제를 코드베이스 전체에서 통일 처리

**상세**:
- `app/core/claude_utils.py` 공통 모듈 생성
- 5개 서비스 파일 리팩토링 (content_transformer, product_image_analyzer, viral_predictor, youtube_comment_autopilot, shorts_extractor)
- test_bombs.py 실패 수정

**난이도**: 하 **재사용**: 높음 (공통 유틸) **예상 시간**: 1시간
### ~~B08. Claude JSON 응답 파싱 통일~~ ✅ 완료 (2026-04-11)

### B09. Sentry 테스트 업데이트

**설명**: `test_observability.py::test_sentry_init_calls_sdk_when_dsn_present`가 
Celery + Redis integration 추가 후 업데이트 안 됨

**난이도**: 하
**예상 시간**: 5분
**전제조건**: 없음
**우선순위 메모**: 배포 영향 없음. 나중에 정리.


### B10. Google Sheets 통합 기반 (Phase 1 - 읽기)

**설명**: yt-factory가 기록하는 Google Sheets 작업 시트를 ContentFlow가 읽을 수 있는 기반 구축

**상세**:
- `app/services/google_sheets.py` — GoogleSheetsClient (서비스 계정 인증, read_sheet, read_sheet_as_dicts)
- Settings에 GOOGLE_SERVICE_ACCOUNT_JSON_PATH / GOOGLE_SERVICE_ACCOUNT_JSON 추가
- 읽기 전용. 쓰기/감시는 다음 단계.

**난이도**: 하 **재사용**: 높음 (Sheets 연동 기반) **예상 시간**: 1~2시간
**전제조건**: 없음 **우선순위 메모**: yt-factory ↔ ContentFlow 연결의 첫 단계.

---

### ~~B16. 썸네일 업로드 검증~~ 완료 (2026-04-12)

**설명**: B11에서 구현한 `_set_thumbnail()`의 실제 동작을 READY_UPLOAD 실데이터로 검증.

**검증 결과**:
- Queue job `fc4db088-c6e7-400e-8661-e959f8b90df9`를 private으로 실제 업로드
- YouTube video `cOFZ2fmSnuM` 생성, `thumbnail_set_success` 로그 확인
- YouTube Data API에서 `privacyStatus=private`, `uploadStatus=processed`, `maxres` thumbnail 확인
- 썸네일 없는 READY_UPLOAD 잡은 계속 스킵 가능, 썸네일 업로드 실패도 non-fatal 유지

**후속 보강**:
- Drive metadata 기준으로 썸네일 파일 suffix 보존 (`.png` 대응)
- 테스트 추가: thumbnail download failure non-fatal, png Content-Type 검증

---

### B18. 플랫폼별 설정 시스템

**설명**: 사용자별·플랫폼별 발행 설정을 관리하는 통합 설정 시스템

**상세**:
- 사용자 공통: 발행 시간대, AI 톤, 알림, 기본 언어
- 네이버 블로그: 스타일(정보형/일상형/리뷰형), 카테고리, 공개범위, 기본 해시태그, 이미지 개수, 인용구 스타일, 다른 채널 안내 링크+CTA
- YouTube: privacy, 카테고리, 기본 태그, 자막 자동업로드
- 공통 채널 안내: 각 플랫폼 링크+문구 자동 삽입

**난이도**: 중 **예상 시간**: 4\~6시간
**전제조건**: 없음

---

### B19. 카드뉴스 자동 생성기 (Instagram/Threads)

**설명**: YouTube 자막에서 핵심 내용을 추출하여 카드뉴스 이미지를 자동 생성하고 Instagram/Threads에 발행

**상세**:
- YouTube 자막 → Claude로 핵심 10장 추출
- HTML 템플릿 → Playwright로 PNG 렌더링
- 설정: 카드 장수(5/10/15), 배경 스타일, 폰트, 색상 테마, 로고/워터마크, CTA 문구("유튜브에서 풀영상 보기"), 카드 비율(1:1 / 4:5)
- 마지막 카드: 채널 안내 + QR코드 또는 링크
- Instagram/Threads 어댑터 연결

**난이도**: 중\~상 **예상 시간**: 8\~12시간
**전제조건**: B18 (설정 시스템)
**참조**: `docs/references/card-news-guide.md` (content-pipeline 프로젝트에서 벤치마킹)

---

### B20. 이미지 생성 Gemini 업그레이드

**설명**: 블로그/카드뉴스 이미지 생성을 pollinations.ai → Google Gemini (google-genai SDK)로 업그레이드

**상세**:
- 현재: pollinations.ai (무료, 품질 불안정, 타임아웃 잦음)
- 변경: google-genai SDK + Gemini 3 Pro (무료 티어 존재, 고품질)
- pollinations.ai는 fallback으로 유지
- content-pipeline의 `generate_image.py` 패턴 참고 (generate/edit/chat 3모드, thinking fallback, 에러 핸들링)
- `blog_image_generator.py`에 이미지 프로바이더 추상화 적용

**난이도**: 하\~중 **예상 시간**: 2\~3시간
**전제조건**: Google AI Studio API 키 발급

---

### B21. 스레드 일일 자동 발행

**설명**: Claude가 매일 스레드 글 5개 자동 생성 + 발행

**상세**:
- Claude가 채널 주제 기반으로 스레드 글 5개 생성
- 글 형식: 후킹 첫 줄 + 본문 3~5줄 + 해시태그
- Celery beat로 하루 분산 발행 (오전/점심/오후/저녁/밤)
- 발행 결과 Supabase 저장 (post_id, 발행시각, 플랫폼)
- 채널별 톤/주제 설정 (B18 설정 시스템 연동)

**난이도**: 중 **예상 시간**: 4~6시간
**전제조건**: B18 (설정 시스템), Threads OAuth 연결

---

### B22. 스레드 반응 분석 → 쇼츠 대본 자동 변환

**설명**: 일주일치 스레드 반응 수집 → 상위 글을 쇼츠 대본+썸네일로 변환

**상세**:
- Threads API로 좋아요/공유/조회수 수집
- 상위 3~5개 글 선별 (반응 점수 계산)
- Claude로 쇼츠 대본 생성 (30~60초 분량)
  * 후킹 오프닝 3초
  * 핵심 내용 전달
  * CTA (팔로우/구독 유도)
- 썸네일 텍스트 후보 3개 생성
- yt-factory Queue에 쇼츠 작업 추가 (READY_GENERATE)
- 매주 월요일 자동 실행 (Celery beat)

**난이도**: 중~상 **예상 시간**: 6~8시간
**전제조건**: B21 (스레드 발행), yt-factory 연동

---

### B23. 쇼츠 다채널 동시 배포

**설명**: yt-factory가 만든 쇼츠를 5개 플랫폼에 동시 배포

**상세**:
- YouTube Shorts
- Instagram Reels
- TikTok
- 네이버 클립
- 카카오톡 숏폼
- 각 플랫폼별 캡션/해시태그 Claude로 최적화
- 배포 결과 통합 대시보드 기록

**난이도**: 상 **예상 시간**: 10~15시간
**전제조건**: B17 (다채널 동시 배포 기반), 각 플랫폼 OAuth

---

### B24. 반응 좋은 쇼츠 → 유튜브 롱폼 확장 파이프라인

**설명**: 쇼츠 반응 데이터 기반으로 롱폼 주제 자동 선정 + yt-factory에 작업 추가

**상세**:
- 쇼츠 성과 수집 (조회수, 좋아요, 댓글, 공유)
- 성과 임계값 초과 시 자동 플래그 (예: 조회수 1만+)
- Claude로 롱폼 확장 기획서 생성
  * 쇼츠 핵심 내용 → 10~15분 롱폼 구성안
  * 섹션별 소제목 + 내용 요약
  * 예상 키워드/태그
- yt-factory Queue에 롱폼 작업 추가
- 사장님 승인 후 생성 시작 (review_mode: manual)

**난이도**: 상 **예상 시간**: 8~10시간
**전제조건**: B22, B23, yt-factory 연동

---

## 🔄 콘텐츠 플라이휠 전략 (사장님 아이디어)

> 스레드 글 → 반응 분석 → 쇼츠 → 다채널 배포 → 롱폼 확장 → 다시 블로그/스레드로

B21 → B22 → B23 → B24 순서로 구현하면
"스레드 글 하나가 유튜브 롱폼까지 자동으로 발전하는" 완전 자동화 플라이휠 완성.

---

## 🏆 제안 우선순위 (Claude 의견)

1. **B07** (자막 추출) — 모든 것의 전제조건, 쉬움
2. **B01** (yt-factory 연동) — OSMU 엔진 연결
3. **B02** (블로그 다채널) — 한국 특화 가치
4. **B03 Instagram만** (쇼츠 배포) — 다채널 시작
5. **B04** (카드뉴스) — Instagram 트래픽 확대
6. **B05** (벤치마킹) — 기획 도구
7. **B06** (쿠팡 쇼츠) — 마지막

**근거**:

- B07은 1\~2시간짜리 기반 작업
- B01은 이미 코드 반쯤 있음
- B02, B03, B04는 가치 있는 기능들이지만 B01 이후
- B05는 독립적이라 언제든 추가 가능
- B06는 리스크 크고 의존성 많음

**하지만 최종 결정은 사장님**. 위는 참고일 뿐.

---

## 📝 백로그 업데이트 규칙

1. 새 아이디어는 항상 **B##** 형식으로 번호 매김
2. 제목은 한 줄로 명확히
3. 난이도/재사용/시간/의존성 필수 기입
4. 현재 스프린트로 이동 시 이 파일에서 "Current Sprint" 섹션으로 이동
5. 완료된 항목은 `docs/COMPLETED.md`로 이동 (있으면)
