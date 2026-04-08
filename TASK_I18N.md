# TASK: 다국어 지원 (i18n) — 한국어/영어/일본어

> 담당: 코드2
> 우선순위: P0 (한국 시장 + 글로벌 확장 필수)

---

## 배경

ContentFlow는 한국 시장이 주력이지만 글로벌 진출도 목표다. 지금 모든 UI와 메시지가 영어로만 되어 있어서 한국 사용자가 진입 장벽을 느낀다.

이 작업은:
1. 한국어 기본 + 영어/일본어 추가
2. 사용자가 언어 선택 가능
3. 대시보드, 랜딩페이지, 이메일, API 에러 메시지 모두 다국어화

---

## 작업 1: 대시보드 i18n 셋업

### 패키지: `next-intl`

```bash
cd dashboard && npm install next-intl
```

### 디렉토리 구조

```
dashboard/
├── messages/
│   ├── ko.json     # 한국어 (기본)
│   ├── en.json     # 영어
│   └── ja.json     # 일본어
├── i18n/
│   ├── routing.ts
│   ├── request.ts
│   └── navigation.ts
├── middleware.ts   # 언어 라우팅
└── app/
    └── [locale]/   # 언어별 라우트
        └── ...     # 기존 페이지들 이동
```

URL 구조:
- `/ko/dashboard` → 한국어
- `/en/dashboard` → 영어
- `/ja/dashboard` → 일본어
- `/dashboard` → 사용자 브라우저 언어 자동 감지

---

## 작업 2: 번역 키 정의

### 파일: `dashboard/messages/ko.json`

```json
{
  "common": {
    "loading": "불러오는 중...",
    "error": "오류가 발생했습니다",
    "save": "저장",
    "cancel": "취소",
    "delete": "삭제",
    "edit": "수정",
    "create": "생성",
    "search": "검색",
    "filter": "필터",
    "all": "전체",
    "none": "없음"
  },
  "nav": {
    "home": "홈",
    "posts": "포스트",
    "videos": "영상",
    "accounts": "계정",
    "analytics": "분석",
    "webhooks": "웹훅",
    "api_keys": "API 키",
    "billing": "결제",
    "settings": "설정"
  },
  "auth": {
    "login": "로그인",
    "signup": "가입하기",
    "logout": "로그아웃",
    "email": "이메일",
    "password": "비밀번호",
    "forgot_password": "비밀번호를 잊으셨나요?",
    "verify_email": "이메일 인증",
    "verify_email_sent": "인증 메일을 보냈습니다"
  },
  "dashboard": {
    "welcome": "환영합니다",
    "this_month": "이번 달",
    "posts_published": "게시된 포스트",
    "videos_generated": "생성된 영상",
    "api_calls": "API 호출",
    "active_accounts": "활성 계정",
    "recent_activity": "최근 활동",
    "quick_actions": "빠른 작업"
  },
  "posts": {
    "title": "포스트",
    "new_post": "새 포스트",
    "post_text": "포스트 내용",
    "platforms": "플랫폼",
    "media": "미디어",
    "scheduled_for": "예약 시간",
    "publish_now": "즉시 게시",
    "schedule": "예약",
    "draft": "임시저장",
    "published": "게시됨",
    "failed": "실패",
    "scheduled": "예약됨",
    "select_platforms": "플랫폼 선택",
    "drag_drop_media": "미디어를 끌어다 놓거나 클릭해서 업로드",
    "preview": "미리보기"
  },
  "videos": {
    "title": "AI 영상",
    "new_video": "새 영상",
    "topic": "주제",
    "topic_placeholder": "어떤 주제로 영상을 만들까요?",
    "mode": "모드",
    "language": "언어",
    "format": "포맷",
    "style": "스타일",
    "template": "템플릿",
    "auto_publish": "자동 배포",
    "generating": "생성 중...",
    "completed": "완료",
    "estimated_time": "예상 시간"
  },
  "accounts": {
    "title": "소셜 계정",
    "connect": "연결",
    "disconnect": "연결 해제",
    "connected": "연결됨",
    "expired": "토큰 만료",
    "reconnect": "재연결"
  },
  "analytics": {
    "title": "분석",
    "period": "기간",
    "last_7_days": "지난 7일",
    "last_30_days": "지난 30일",
    "last_90_days": "지난 90일",
    "total_views": "총 조회수",
    "total_likes": "총 좋아요",
    "total_shares": "총 공유",
    "engagement_rate": "참여율",
    "top_posts": "상위 포스트",
    "platform_comparison": "플랫폼 비교"
  },
  "billing": {
    "title": "결제",
    "current_plan": "현재 플랜",
    "next_billing": "다음 결제일",
    "usage": "사용량",
    "upgrade": "업그레이드",
    "cancel_subscription": "구독 취소",
    "billing_history": "결제 이력",
    "free": "무료",
    "build": "빌드",
    "scale": "스케일",
    "enterprise": "엔터프라이즈"
  },
  "settings": {
    "title": "설정",
    "profile": "프로필",
    "name": "이름",
    "email": "이메일",
    "change_password": "비밀번호 변경",
    "notifications": "알림",
    "language": "언어",
    "theme": "테마",
    "team": "팀",
    "danger_zone": "위험 영역",
    "delete_account": "계정 삭제"
  },
  "errors": {
    "required": "필수 항목입니다",
    "invalid_email": "올바른 이메일 형식이 아닙니다",
    "password_too_short": "비밀번호는 8자 이상이어야 합니다",
    "passwords_dont_match": "비밀번호가 일치하지 않습니다",
    "network_error": "네트워크 오류가 발생했습니다",
    "unauthorized": "로그인이 필요합니다",
    "forbidden": "권한이 없습니다",
    "not_found": "찾을 수 없습니다",
    "rate_limit": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요"
  }
}
```

### `messages/en.json` — 영어 번역
### `messages/ja.json` — 일본어 번역

모든 키를 동일하게 유지, 값만 번역.

---

## 작업 3: 컴포넌트 i18n 적용

### 모든 페이지/컴포넌트에서 번역 사용

```tsx
import { useTranslations } from 'next-intl';

export default function PostsPage() {
  const t = useTranslations('posts');
  
  return (
    <div>
      <h1>{t('title')}</h1>
      <button>{t('new_post')}</button>
    </div>
  );
}
```

### 17개 페이지 모두 적용
- 홈, 포스트, 영상, 계정, 분석, 웹훅, API 키, 결제, 설정
- 인증 페이지
- 모든 모달, 폼, 에러 메시지

---

## 작업 4: 언어 전환 UI

### 파일: `dashboard/components/language-switcher.tsx`

- 헤더 우측에 언어 드롭다운
- 국기 아이콘 + 언어 이름 (🇰🇷 한국어, 🇺🇸 English, 🇯🇵 日本語)
- 선택 시 URL의 locale 변경 + 사용자 설정 저장
- 사용자 프로필에 language 필드 추가

---

## 작업 5: 랜딩페이지 i18n

### 디렉토리: `landing/`

랜딩페이지도 동일하게 i18n 적용:
- `landing/messages/ko.json`, `en.json`, `ja.json`
- 헤로 헤드라인, 기능 설명, 가격, FAQ 모두 번역
- 한국어를 기본으로 (`/`)
- `/en`, `/ja`로 다른 언어 접근

### 한국어 카피 (예시)
- "1개 주제로 21개 플랫폼에 한 번에 게시"
- "AI가 영상 만들고, 댓글도 답해주는 자판기"
- "지금 무료로 시작하기"

영어/일본어는 톤을 맞춰서 번역.

---

## 작업 6: 이메일 템플릿 다국어화

### 파일: `app/templates/emails/`

기존 10개 템플릿을 각 언어별로 작성:

```
templates/emails/
├── ko/
│   ├── welcome.html
│   ├── payment_succeeded.html
│   └── ...
├── en/
│   └── ... (이미 있는 영어 버전)
└── ja/
    └── ...
```

### 백엔드 수정 (`app/services/email_service.py`)

- 사용자의 language 설정에 따라 템플릿 선택
- 기본은 영어 (없으면 fallback)

---

## 작업 7: API 에러 메시지 다국어화

### 파일: `app/core/i18n.py`

API 응답에서 에러 메시지도 사용자 언어로:

- 요청 헤더 `Accept-Language`로 언어 감지
- 또는 사용자 프로필의 language 사용
- 에러 코드는 영어 (변경 없음), 메시지만 번역

```python
ERROR_MESSAGES = {
    "QUOTA_EXCEEDED": {
        "ko": "월간 사용량 한도를 초과했습니다. 플랜을 업그레이드해주세요.",
        "en": "Monthly quota exceeded. Please upgrade your plan.",
        "ja": "月間クォータを超過しました。プランをアップグレードしてください。",
    },
    # ...
}
```

---

## 작업 8: 사용자 언어 설정 저장

### DB 수정 (`app/models/schemas.py`)

users 테이블에 추가:
- `language` (TEXT) — 'ko' / 'en' / 'ja' / null
- `timezone` (TEXT) — 'Asia/Seoul' / 'America/New_York' 등

### API
- `PATCH /api/v1/users/me` — language, timezone 변경 가능
- 가입 시 브라우저 Accept-Language로 자동 설정

---

## 작업 9: 날짜/시간/숫자 포맷

### 파일: `dashboard/lib/format.ts`

언어/지역에 따라 자동 포맷:

```typescript
import { useFormatter } from 'next-intl';

const format = useFormatter();
format.dateTime(date, { dateStyle: 'long' });  // 한국: "2026년 4월 8일"
format.number(1234567);                          // 한국: "1,234,567"
format.relativeTime(date);                       // 한국: "3시간 전"
```

타임존도 사용자 설정 따라 표시.

---

## 작업 10: 테스트

- 각 언어로 페이지 렌더링 테스트
- 언어 전환 동작 테스트
- 이메일 템플릿 렌더링 (3개 언어)
- API 에러 메시지 (3개 언어)
- 누락된 번역 키 자동 검출 스크립트

### 파일: `scripts/check_translations.py`
- 한국어 키를 기준으로 영어/일본어에 누락된 키 찾기
- CI에서 자동 실행

---

## 완료 기준

- [ ] next-intl 셋업
- [ ] 한국어/영어/일본어 메시지 파일
- [ ] 17개 대시보드 페이지 i18n 적용
- [ ] 언어 전환 UI
- [ ] 랜딩페이지 i18n
- [ ] 이메일 템플릿 3개 언어
- [ ] API 에러 메시지 다국어화
- [ ] 사용자 언어/타임존 설정
- [ ] 날짜/시간/숫자 포맷
- [ ] 누락 번역 검출 스크립트
- [ ] 백엔드 ruff + pytest 통과
- [ ] 대시보드 + 랜딩 빌드 통과

---

## 의미

이거 끝나면 ContentFlow가:

1. **한국 사용자가 진짜 편하게 쓸 수 있는 제품** (모든 UI 한국어)
2. **글로벌 출시 준비 완료** (영어 동시 지원)
3. **일본 시장 진입 가능** (3국어 지원으로 아시아 커버)

Zernio는 영어만 지원한다. ContentFlow가 한국어 + 일본어로 차별화하면 아시아 시장에서 압도적 우위를 가진다.

특히 한국어 자연스러운 카피는 ContentFlow만의 무기가 된다. ("자판기" 같은 친근한 표현, "21개 플랫폼에 한 방에" 같은 임팩트 있는 문구.)
