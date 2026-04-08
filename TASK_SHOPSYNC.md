# TASK: ShopSync — 한국 쇼핑몰 셀러 특화 제품

> 담당: 코드2
> 선행 조건: TASK_VERTICAL_LAUNCHER.md (코드3 작업) 완료 후
> 우선순위: P0 (두 번째 버티컬 제품)

---

## 배경

ContentFlow 엔진 위에 올라가는 두 번째 버티컬 제품. 타겟은 **네이버 스마트스토어 + 쿠팡 + 11번가 셀러**.

### 한 문장 포지셔닝

> **"신상품 사진 1장 → 전 채널 콘텐츠 10분 컷. 한국 쇼핑몰 셀러를 위한 AI 콘텐츠 자판기."**

### 기존 한국 SaaS와 차별점

- **샵링커, 셀러툴 등**: 재고/가격/주문 동기화 전문 (우리는 안 함)
- **카페24, 고도몰**: 쇼핑몰 솔루션 (우리는 안 함)
- **ShopSync (우리)**: 신상품 한 개 올리면 전 채널 콘텐츠 자동 생성 (이 영역에 경쟁자 없음)

셀러가 신상품 올릴 때 6~8시간 걸리던 작업을 **10분**으로 줄이는 게 핵심 가치.

---

## 핵심 기능: Product Content Bomb

**상품 이미지 1장 업로드 → AI가 전 채널 콘텐츠 자동 생성:**

1. 스마트스토어 상세페이지 HTML
2. 쿠팡/11번가 상품 설명
3. 인스타 캐러셀 10장 (썸네일 + 포인트 카드)
4. 블로그 포스트 (네이버/티스토리 SEO 최적화)
5. 유튜브 쇼츠 스크립트
6. 카카오채널 알림 메시지

이 하나의 기능에 모든 리소스를 집중한다. 다른 기능(재고 동기화, 가격 변동, CS 응답 등)은 의도적으로 제외한다.

---

## 작업 1: 버티컬 스캐폴딩

TASK_VERTICAL_LAUNCHER.md가 완료된 후, 첫 단계:

```bash
pnpm create vertical shopsync
```

### verticals/shopsync/config.json

```json
{
  "id": "shopsync",
  "name": "ShopSync",
  "tagline": "신상품 사진 1장 → 전 채널 콘텐츠 10분 컷",
  "description": "한국 쇼핑몰 셀러를 위한 AI 콘텐츠 자동화. 네이버 스마트스토어, 쿠팡, 인스타, 블로그까지 한 번에.",
  
  "brand": {
    "colors": {
      "primary": "#FF6B35",
      "secondary": "#FFD23F",
      "accent": "#00C896",
      "bg": "#0F0F0F",
      "text": "#FFFFFF"
    }
  },
  
  "target": {
    "persona": "한국 쇼핑몰 셀러 (스마트스토어/쿠팡/11번가)",
    "language": ["ko"],
    "region": ["KR"]
  },
  
  "pricing": {
    "currency": "KRW",
    "plans": [
      {
        "id": "starter",
        "name": "스타터",
        "price_monthly": 0,
        "features": ["월 5개 상품", "3개 채널", "기본 템플릿"]
      },
      {
        "id": "seller",
        "name": "셀러",
        "price_monthly": 49000,
        "features": ["월 100개 상품", "무제한 채널", "프리미엄 템플릿", "상품 이미지 자동 편집"]
      },
      {
        "id": "power_seller",
        "name": "파워셀러",
        "price_monthly": 99000,
        "features": ["무제한 상품", "화이트라벨", "API 접근", "전담 지원"]
      }
    ]
  },
  
  "features": {
    "core": [
      "product_content_bomb",
      "smart_store_integration",
      "coupang_integration",
      "naver_blog_seo"
    ],
    "platforms_enabled": [
      "naver_blog", "tistory", "kakao", "instagram", "facebook",
      "naver_smart_store", "coupang", "eleven_street"
    ],
    "platforms_hero": [
      "naver_smart_store", "coupang", "instagram", "naver_blog"
    ]
  },
  
  "landing": {
    "hero": {
      "headline": "신상품 사진 1장.\n전 채널 콘텐츠 10분 컷.",
      "sub": "스마트스토어, 쿠팡, 인스타, 블로그까지 AI가 알아서. 셀러의 시간을 돌려드립니다.",
      "cta_primary": "무료로 시작하기",
      "cta_secondary": "데모 보기"
    }
  },
  
  "dashboard": {
    "home_widgets": [
      "products_this_month",
      "channel_distribution",
      "time_saved",
      "top_performing_products"
    ],
    "nav": [
      "home",
      "products",
      "content_library",
      "channels",
      "analytics",
      "settings"
    ],
    "onboarding_steps": [
      "connect_smart_store",
      "connect_first_sns",
      "upload_first_product",
      "review_generated_content"
    ]
  }
}
```

---

## 작업 2: Product Content Bomb 엔진

### 파일: `app/services/product_bomb.py`

핵심 서비스. 상품 이미지 + 최소 정보 → 전 채널 콘텐츠 자동 생성.

```python
class ProductBomb:
    async def generate(
        self,
        product_images: list[str],  # URL 또는 base64
        product_name: str,
        price: int,
        category: str,
        target_platforms: list[str],
        user_id: str,
    ) -> ProductBombResult:
        """
        상품 정보 → 전 채널 콘텐츠 생성.
        
        단계:
        1. 이미지 분석 (Claude Vision)
           - 상품 특징 추출 (색상, 재질, 사이즈, 용도)
           - 타겟 고객 추론
           - 셀링 포인트 자동 추출
        
        2. 채널별 콘텐츠 생성 (병렬)
           - 스마트스토어 상세페이지 HTML
           - 인스타 캐러셀 (이미지 + 텍스트 카드)
           - 블로그 포스트 (SEO 최적화)
           - 쿠팡/11번가 상품 설명
           - 카카오 알림 메시지
        
        3. 결과 검증 (품질 체크)
        
        4. 미리보기 + 승인 대기 상태로 저장
        """
```

### 이미지 분석 모듈: `app/services/product_image_analyzer.py`

Claude Vision API 사용:

```python
async def analyze_product(images: list[bytes]) -> ProductAnalysis:
    """
    상품 이미지 → 구조화된 분석 결과.
    
    반환:
    - main_color, material, style
    - target_audience
    - use_cases[]
    - selling_points[]
    - suggested_keywords[]
    - suggested_hashtags[]
    """
```

### 채널별 렌더러: `app/services/channel_renderers/`

각 채널별로 별도 파일:
- `smart_store_renderer.py` — 상세페이지 HTML
- `coupang_renderer.py` — 쿠팡 상품 설명
- `instagram_renderer.py` — 캐러셀 구성
- `naver_blog_renderer.py` — 블로그 포스트 (SEO 최적화)
- `kakao_renderer.py` — 알림 메시지

각 렌더러는 `ProductAnalysis` + 템플릿을 받아서 해당 채널 포맷으로 변환.

---

## 작업 3: 네이버 스마트스토어 어댑터

### 파일: `app/adapters/naver_smart_store.py`

네이버 커머스 API 기반 상품 등록.

```python
class NaverSmartStoreAdapter(PlatformAdapter):
    platform_name = "naver_smart_store"
    supports_video = False
    supports_image = True
    max_text_length = 50000  # 상세페이지 HTML
    
    async def publish(self, account: AccountInfo, payload: PostPayload) -> PostResult:
        """
        상품 등록.
        
        payload.platform_options에 필요한 필드:
        - product_name
        - price
        - stock_quantity
        - category_id
        - detail_content (HTML)
        - images[]
        """
        # Naver Commerce API 호출
```

### OAuth 프로바이더: `app/oauth/providers/naver_commerce.py`

네이버 커머스 API는 별도 인증 체계. OAuth 2.0이지만 스코프가 다름.

---

## 작업 4: 쿠팡 WING 어댑터 (선택)

### 파일: `app/adapters/coupang_wing.py`

쿠팡 WING Open API 기반. 단, 셀러 승인 절차가 까다로우니 **v1에서는 mock만 구현**하고 실제 연동은 v2로 미룬다.

```python
class CoupangWingAdapter(PlatformAdapter):
    platform_name = "coupang_wing"
    # v1: mock 구현
    # v2: 실제 API 연동
```

---

## 작업 5: ShopSync 전용 대시보드 UI

### 디렉토리: `verticals/shopsync/dashboard/`

본체 대시보드를 기반으로 하되, **상품 중심**으로 재구성:

### 홈 대시보드
- "이번 달 등록 상품": 25개
- "절약한 시간": 125시간
- "채널별 트래픽": 인포그래픽
- "베스트 상품 TOP 10"

### 상품 등록 페이지 (가장 중요)
- 드래그앤드롭 이미지 업로드 (최대 10장)
- 상품명 + 가격 + 카테고리 입력 (최소 필수)
- "Generate Content Bomb" 버튼 1개
- 진행 상황 실시간 표시:
  - ✓ 이미지 분석 완료 (3초)
  - ✓ 스마트스토어 상세페이지 (8초)
  - ✓ 인스타 캐러셀 (12초)
  - ✓ 블로그 포스트 (15초)
  - ⏳ 카카오 메시지...
- 각 채널별 미리보기 탭
- "승인 후 배포" / "수정" 버튼

### 콘텐츠 라이브러리
- 생성된 콘텐츠 히스토리
- 재사용 가능한 템플릿
- 브랜드 가이드 (로고, 컬러, 폰트)

---

## 작업 6: ShopSync 랜딩페이지

### 디렉토리: `verticals/shopsync/landing/`

Hero 카피:

```
신상품 사진 1장.
전 채널 콘텐츠 10분 컷.

스마트스토어, 쿠팡, 인스타, 블로그까지
AI가 알아서 맞춰드립니다.

[무료로 시작하기]  [데모 보기]

⭐ "하루 8시간 → 10분. 진짜예요" — 스마트스토어 셀러 박OO
```

섹션:
1. **Before/After 비교**: "예전엔 이렇게 6시간 → 지금은 10분"
2. **작동 방식 데모**: 이미지 업로드 → 결과 미리보기 (실제 작동)
3. **지원 채널**: 8개 플랫폼 로고 (한국 특화 강조)
4. **가격**: 3단 카드 (원화)
5. **셀러 후기**: placeholder로 준비
6. **FAQ**: 한국 셀러가 자주 묻는 질문

---

## 작업 7: 테스트

- `tests/test_product_bomb.py`
  - 이미지 분석 mock
  - 채널별 렌더러
  - 전체 플로우 end-to-end (mock)
- `tests/test_naver_smart_store.py`
  - 상품 등록 flow
- `verticals/shopsync/`에 대한 E2E 테스트 (선택)

---

## 완료 기준

- [ ] `verticals/shopsync/` 스캐폴딩 (TASK_VERTICAL_LAUNCHER 선행)
- [ ] `config.json` 작성 (ShopSync 브랜드, 가격, 기능)
- [ ] `app/services/product_bomb.py` — 핵심 엔진
- [ ] `app/services/product_image_analyzer.py` — Claude Vision 통합
- [ ] `app/services/channel_renderers/` — 5개 렌더러
- [ ] `app/adapters/naver_smart_store.py` — 네이버 커머스 어댑터
- [ ] `app/oauth/providers/naver_commerce.py` — 네이버 커머스 OAuth
- [ ] `app/adapters/coupang_wing.py` — 쿠팡 mock 어댑터
- [ ] `verticals/shopsync/dashboard/` — 상품 중심 UI
- [ ] `verticals/shopsync/landing/` — 한국어 랜딩페이지
- [ ] 테스트 추가
- [ ] ruff + pytest 통과
- [ ] `verticals/shopsync/` 빌드 통과

---

## 의도적으로 제외되는 것

이것들은 **v1에 절대 넣지 않는다**. 핵심 메시지가 흐려지기 때문:

- ❌ 재고 동기화 (샵링커 영역)
- ❌ 가격 변동 추적
- ❌ 주문 관리
- ❌ CS 자동 응답
- ❌ 리뷰 크로스 포스팅 (v2에서 고려)
- ❌ 배송 추적

v1은 **"상품 한 개 등록 → 전 채널 콘텐츠 자동 생성"** 이 한 가지에만 집중한다.

---

## 의미

ShopSync가 성공하면:
- 한국 쇼핑몰 시장 (수십만 셀러)에 진입
- ARPU ₩49,000 (셀러 기준 저렴)
- **경쟁자 없는 영역** (콘텐츠 생성 자동화는 한국에 아무도 안 함)
- ContentFlow의 한국 특화 어댑터(네이버, 티스토리, 카카오) 가치가 빛남

실패해도 ContentFlow 본체에 흡수 가능. 버티컬 아키텍처의 장점.
