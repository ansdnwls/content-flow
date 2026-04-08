# TASK: YtBoost — 유튜버 증폭기 (백엔드)

> 담당: 코덱2
> 선행 조건: Vertical Launcher 템플릿 완료 후 프론트 작업. 백엔드는 지금 시작.
> 우선순위: P0 (사장님 독밥푸드 대상, 첫 번째 런칭 제품)

---

## 배경

ContentFlow 엔진 위에 올라가는 **첫 번째 버티컬 제품**. 타겟은 **구독자 1천~10만 규모의 유튜버**.

### 한 문장 포지셔닝

> **"Upload once. Ship everywhere. 유튜브 영상 하나가 18곳의 콘텐츠가 됩니다."**

### 사장님 독밥푸드

사장님이 yt-factory로 생성한 영상을 YtBoost로 자동 배포하는 구조. **사장님이 첫 번째 고객**이자 지속적인 품질 피드백 소스다.

이게 엄청난 장점이다: Stripe, Linear, Vercel 모두 독밥푸드로 시작해서 컸다.

---

## 핵심 기능 4가지

다른 모든 아이디어는 의도적으로 제외한다. 이 4개에만 집중한다.

1. **YouTube 업로드 트리거** — 유튜브에 영상 올리면 자동 감지
2. **Auto Shorts Extraction** — AI가 훅 구간 찾아서 60초 쇼츠 3개 자동 추출
3. **Multi-Platform Distribution** — 유튜브 쇼츠 + 인스타 릴스 + 틱톡 + X + Threads + 페이스북 동시 배포
4. **Comment Autopilot for YouTube** — 댓글 자동 답변 (AI, 승인 모드)

---

## 작업 1: YouTube 업로드 트리거

### 파일: `app/services/youtube_trigger.py`

유튜브에 새 영상 올라간 걸 감지하는 시스템.

### 방법 A: YouTube PubSubHubbub (권장)
- YouTube 공식 실시간 알림 시스템
- RSS 기반 webhook
- 유튜브 채널 구독 → 새 영상 올라오면 즉시 알림
- 지연 시간: 수 분 이내

```python
async def subscribe_to_channel(channel_id: str, user_id: str):
    """
    YouTube PubSubHubbub 구독.
    
    POST https://pubsubhubbub.appspot.com/subscribe
    hub.mode=subscribe
    hub.topic=https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}
    hub.callback=https://api.ytboost.dev/api/webhooks/youtube/{user_id}
    """
```

### 방법 B: YouTube Data API 폴링 (백업)
- 5분마다 사용자의 유튜브 채널 최신 영상 확인
- PubSubHubbub 실패 시 fallback
- Celery Beat task

### 엔드포인트: `app/api/webhooks/youtube.py`

```python
@router.post("/youtube/{user_id}")
async def youtube_webhook(user_id: str, request: Request):
    """
    PubSubHubbub 알림 수신.
    
    1. HMAC 검증
    2. XML 파싱 → 새 video_id 추출
    3. 기존에 처리한 영상인지 확인 (dedup)
    4. Shorts extraction task 큐잉
    """
```

---

## 작업 2: Auto Shorts Extraction

### 파일: `app/services/shorts_extractor.py`

롱폼 유튜브 영상 → 60초 쇼츠 3개 자동 추출.

### 알고리즘

```python
async def extract_shorts(video_id: str, user_id: str) -> list[ShortClip]:
    """
    1. YouTube API로 영상 메타데이터 가져오기
       - 제목, 설명, 길이, 자막(caption)
    
    2. 자막 다운로드 (timestamp 포함)
       - YouTube Transcript API 또는 공식 caption API
    
    3. Claude API로 훅 구간 찾기
       - 전체 transcript를 주고:
       - "이 영상에서 가장 임팩트 있는 3구간을 찾아라"
       - "각 구간은 45-60초, 자체 완결적이어야 한다"
       - 출력: [{start, end, hook, reason}, ...]
    
    4. 각 구간을 yt-factory에 전달해서 쇼츠 생성
       - 또는 ffmpeg로 직접 crop + 자막 burn
    
    5. 결과 저장 + 승인 대기 상태로
    """
```

### 훅 선택 기준 (Claude 프롬프트)

```
다음 유튜브 영상 자막에서 60초 쇼츠로 만들기 좋은 구간 3개를 찾아라.

평가 기준:
1. 첫 3초에 후킹이 강한가 (질문, 충격, 반전)
2. 45-60초 안에 완결된 이야기가 되는가
3. 독립적으로 봐도 이해되는가
4. 시청 이탈을 유발하는 긴 설명이 없는가

각 구간에 대해:
- start_seconds, end_seconds
- hook_line (첫 3초 대사)
- reason (왜 좋은지)
- suggested_title (쇼츠용 제목)
- suggested_hashtags (5개)
```

### 파일: `app/workers/shorts_worker.py`

Celery task로 실행.

---

## 작업 3: Multi-Platform Distribution

YtBoost는 이미 있는 ContentFlow 어댑터를 재사용. 새로 만들 필요 없음.

### 파일: `app/services/ytboost_distributor.py`

```python
class YtBoostDistributor:
    """유튜버 전용 배포 서비스."""
    
    PLATFORM_MAP = {
        "youtube_shorts": {"adapter": "youtube", "options": {"is_short": True}},
        "instagram_reels": {"adapter": "instagram", "options": {"media_type": "REELS"}},
        "tiktok": {"adapter": "tiktok", "options": {}},
        "x": {"adapter": "x", "options": {"with_media": True}},
        "threads": {"adapter": "threads", "options": {}},
        "facebook_reels": {"adapter": "facebook", "options": {"media_type": "REELS"}},
    }
    
    async def distribute_short(
        self,
        short_clip: ShortClip,
        target_platforms: list[str],
        user_id: str,
    ) -> list[DistributionResult]:
        """
        쇼츠 하나를 여러 플랫폼에 맞게 변환 + 동시 배포.
        
        - 플랫폼별 최적 해상도/길이 자동 변환
        - 플랫폼별 해시태그 자동 조정
        - 플랫폼별 캡션 재작성 (Claude)
        """
```

---

## 작업 4: Comment Autopilot for YouTube

이미 `app/services/comment_service.py`가 있음. YtBoost용으로 확장.

### 파일: `app/services/youtube_comment_autopilot.py`

```python
class YouTubeCommentAutopilot:
    async def run_for_channel(self, channel_id: str, user_id: str):
        """
        1. 해당 채널의 최근 영상들 조회
        2. 각 영상의 댓글 수집 (YouTube API)
        3. 이미 답변한 댓글은 제외
        4. Claude로 답변 생성 (채널 톤 학습)
        5. 사용자 모드에 따라:
           - auto: 즉시 답변
           - review: 대기열에 넣고 대시보드에서 승인
        6. 승인 후 YouTube API로 답변 작성
        """
```

### 채널 톤 학습

```python
async def learn_channel_tone(channel_id: str) -> ChannelTone:
    """
    크리에이터가 기존에 쓴 답글 100개를 분석해서
    말투, 이모지 사용, 호칭, 길이 등을 학습.
    
    이후 AI 답변 생성 시 이 톤을 참고.
    """
```

---

## 작업 5: YtBoost 전용 DB 테이블

### 파일: `app/models/schemas.py`

신규 테이블:

```sql
-- YtBoost 구독한 유튜브 채널
CREATE TABLE ytboost_subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    youtube_channel_id TEXT NOT NULL,
    channel_name TEXT,
    subscribed_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    auto_distribute BOOLEAN DEFAULT false,
    target_platforms JSONB DEFAULT '[]',
    auto_comment_mode TEXT DEFAULT 'review',  -- 'auto' | 'review'
    UNIQUE(user_id, youtube_channel_id)
);

-- 추출된 쇼츠 클립
CREATE TABLE ytboost_shorts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    source_video_id TEXT NOT NULL,
    source_channel_id TEXT NOT NULL,
    start_seconds INT,
    end_seconds INT,
    hook_line TEXT,
    suggested_title TEXT,
    suggested_hashtags JSONB,
    reason TEXT,
    clip_file_url TEXT,
    status TEXT DEFAULT 'pending',  -- pending | approved | rejected | distributed
    created_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ
);

-- 학습된 채널 톤
CREATE TABLE ytboost_channel_tones (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    youtube_channel_id TEXT NOT NULL,
    tone_profile JSONB,
    sample_size INT,
    learned_at TIMESTAMPTZ,
    UNIQUE(user_id, youtube_channel_id)
);
```

---

## 작업 6: YtBoost API 엔드포인트

### 파일: `app/api/v1/ytboost.py`

```python
# 채널 구독 관리
POST   /api/v1/ytboost/channels              # 유튜브 채널 연동 + 구독
GET    /api/v1/ytboost/channels              # 연동된 채널 목록
PATCH  /api/v1/ytboost/channels/{id}         # 자동화 설정 수정
DELETE /api/v1/ytboost/channels/{id}         # 연동 해제

# 쇼츠 관리
GET    /api/v1/ytboost/shorts                # 추출된 쇼츠 목록
GET    /api/v1/ytboost/shorts/{id}           # 상세
POST   /api/v1/ytboost/shorts/{id}/approve   # 승인 → 배포
POST   /api/v1/ytboost/shorts/{id}/reject    # 거부
POST   /api/v1/ytboost/shorts/extract        # 특정 영상에서 수동 추출

# 댓글 autopilot
GET    /api/v1/ytboost/comments/pending      # 승인 대기 중 답변
POST   /api/v1/ytboost/comments/{id}/approve # 답변 승인
POST   /api/v1/ytboost/comments/{id}/edit    # 답변 수정
```

---

## 작업 7: yt-factory 연결

YtBoost는 **사장님의 yt-factory와 연결**된다.

### 파일: `app/services/yt_factory_integration.py`

```python
class YtFactoryIntegration:
    """
    yt-factory에서 영상이 YouTube에 업로드되면
    자동으로 YtBoost 파이프라인 트리거.
    
    두 가지 방법:
    
    A. yt-factory가 YtBoost webhook 호출
       yt-factory의 publish_agent가 YouTube 업로드 성공 시
       YtBoost API /webhooks/yt-factory 호출
       
    B. YouTube PubSubHubbub 사용 (독립적)
       yt-factory 없이도 작동. 일반 YtBoost 사용자와 동일.
    
    권장: A + B 병행. A가 있으면 더 빠르고 안정적.
    """
```

### 파일: `app/api/webhooks/yt_factory.py`

```python
@router.post("/yt-factory")
async def yt_factory_webhook(payload: YtFactoryPayload):
    """
    yt-factory에서 영상 업로드 완료 시 호출.
    
    payload:
    - yt_factory_job_id
    - youtube_video_id
    - youtube_channel_id
    - script_data (챕터 정보 → 훅 찾기에 도움)
    - user_id (YtBoost 사용자 ID, 매핑)
    """
```

---

## 작업 8: 테스트

- `tests/test_youtube_trigger.py`
- `tests/test_shorts_extractor.py`
  - Claude API mock
  - 다양한 영상 길이 (5분, 30분, 2시간)
- `tests/test_youtube_comment_autopilot.py`
  - 톤 학습
  - 자동 답변 생성
- `tests/test_ytboost_api.py`

---

## 완료 기준

- [ ] YouTube PubSubHubbub 구독 시스템
- [ ] YouTube webhook 핸들러 + HMAC 검증
- [ ] Auto Shorts Extraction (Claude 기반)
- [ ] yt-factory 연결 (webhook)
- [ ] YtBoost Distributor (플랫폼별 자동 변환)
- [ ] YouTube Comment Autopilot (톤 학습 + 자동 답변)
- [ ] DB 테이블 3개 + SQL 마이그레이션
- [ ] API 엔드포인트 12개
- [ ] 테스트 추가
- [ ] ruff + pytest 통과

---

## 의도적으로 제외되는 것

v1에 넣지 않는다:
- ❌ 썸네일 A/B 테스트 (v2)
- ❌ 조회수 예측 (v2)
- ❌ 스폰서 매칭 (v2)
- ❌ 자동 번역 (다른 언어권 진출 시)
- ❌ 쇼츠 수익화 분석 (유튜브 API 복잡)

v1은 **"유튜브 업로드 → 자동 쇼츠 → 멀티 플랫폼 배포 → 댓글 자동 답변"** 한 플로우에만 집중.

---

## 독밥푸드 검증 시나리오

사장님이 테스트하는 시나리오:

```
1. yt-factory에서 ch001 영상 생성 (판례 롱폼)
2. YouTube에 업로드 (기존 yt-factory 플로우)
3. yt-factory webhook → YtBoost에 알림
4. YtBoost가 자막 다운로드 + Claude 호출
5. 쇼츠 3개 추출 (훅 구간 자동 선택)
6. 사장님이 대시보드에서 승인
7. 유튜브 쇼츠 + 인스타 릴스 + 틱톡에 자동 배포
8. 댓글 달리면 자동 답변 생성 (승인 대기)
9. 사장님이 한 번 쓱 훑어보고 승인
```

이 시나리오가 매끄럽게 돌아가면 **YtBoost는 실제 런칭 가능한 수준**이다.

---

## 의미

YtBoost는:
1. **사장님의 첫 고객**: yt-factory 운영에 즉시 가치
2. **Vertical Launcher 검증**: 템플릿이 진짜로 작동하는지 확인
3. **독밥푸드 기반 개선**: 매일 쓰는 제품이라 품질이 보장됨
4. **첫 매출 가능성**: 유튜버 3명 베타 → 월 $29 × 10명 → MRR $290

지금 만든 ContentFlow 엔진의 모든 기능 (Content Bomb, Comment Autopilot, Viral Score, 분석, 결제)이 YtBoost에서 실제로 쓰이게 된다. **이론이 아니라 실전 검증**이다.

코드2가 ShopSync 백엔드 만드는 동안 코덱2가 YtBoost 백엔드 만들면, 2주 안에 **두 버티컬 제품의 백엔드**가 준비된다.
