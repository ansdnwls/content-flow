# TASK: 대시보드 프론트엔드 (Next.js)

> 담당: 코드2
> 우선순위: P0 (실제 사용자 onboarding을 위해 필수)

---

## 배경

ContentFlow는 지금 **API만 있는 상태**다. 개발자는 SDK로 호출할 수 있지만, 일반 사용자는 진입할 길이 없다. 대시보드 UI가 있어야 SaaS 제품으로 팔린다.

이 작업은 사용자가 가입하고, 소셜 계정 연결하고, 포스팅하고, 분석을 보는 **풀 대시보드**를 Next.js로 만드는 것이다.

랜딩페이지(`landing/`)는 이미 있으니 별도 디렉토리(`dashboard/`)에 만든다.

---

## 작업 1: 프로젝트 셋업

### 디렉토리: `dashboard/`

```
dashboard/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   └── verify-email/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx          # 사이드바 + 헤더
│   │   ├── page.tsx             # 홈 (최근 활동)
│   │   ├── posts/
│   │   │   ├── page.tsx         # 포스트 목록
│   │   │   ├── new/page.tsx     # 새 포스트
│   │   │   └── [id]/page.tsx    # 상세
│   │   ├── videos/
│   │   │   ├── page.tsx
│   │   │   └── new/page.tsx
│   │   ├── accounts/page.tsx    # 소셜 계정 연결
│   │   ├── analytics/page.tsx   # 분석
│   │   ├── webhooks/page.tsx
│   │   ├── api-keys/page.tsx
│   │   ├── billing/page.tsx
│   │   └── settings/page.tsx
│   ├── api/
│   │   └── auth/[...nextauth]/route.ts
│   ├── layout.tsx
│   └── globals.css
├── components/
│   ├── ui/                      # shadcn/ui
│   ├── sidebar.tsx
│   ├── header.tsx
│   ├── stat-card.tsx
│   ├── platform-icon.tsx
│   ├── post-composer.tsx
│   ├── video-generator.tsx
│   └── connect-account-button.tsx
├── lib/
│   ├── api-client.ts            # ContentFlow SDK 래퍼
│   ├── auth.ts
│   └── utils.ts
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
└── README.md
```

### 기술 스택
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui (컴포넌트 라이브러리)
- ContentFlow JavaScript SDK 사용 (`sdk/javascript/`)
- NextAuth.js (인증)
- SWR 또는 TanStack Query (데이터 페칭)
- Recharts (차트)
- Lucide icons

### 디자인 톤
- 다크 모드 기본 (랜딩페이지와 통일)
- 그라디언트 액센트 (퍼플 → 블루)
- 반응형 (모바일 사이드바 햄버거)
- shadcn/ui 기본 스타일

---

## 작업 2: 인증 페이지

### `/login`, `/signup`
- 이메일 + 비밀번호
- Google/GitHub OAuth 옵션
- 가입 후 자동 로그인 + 온보딩 페이지로

### `/verify-email`
- 이메일 인증 토큰 처리
- 인증 완료 시 대시보드로

---

## 작업 3: 대시보드 홈

### `/` (대시보드 루트)
- 통계 카드 4개 (이번 달 포스트, 영상, API 호출, 활성 계정)
- 최근 활동 피드 (최근 10개 포스트/영상)
- 빠른 액션 버튼 (새 포스트, 새 영상, 계정 연결)
- 사용량 진행 바 (플랜 한도 대비)

### 사이드바 메뉴
- 홈
- 포스트
- 영상
- 계정
- 분석
- 웹훅
- API 키
- 결제
- 설정

---

## 작업 4: 포스트 관리

### `/posts`
- 포스트 목록 (테이블)
- 필터: 상태, 플랫폼, 날짜
- 검색
- 페이지네이션

### `/posts/new`
- 포스트 작성 폼
- 텍스트 에디터 (마크다운)
- 미디어 업로드 (드래그앤드롭)
- 플랫폼 선택 (체크박스 18개)
- 플랫폼별 옵션 (제목, 태그 등)
- 즉시 발행 vs 예약
- 미리보기 (각 플랫폼별)

### `/posts/[id]`
- 포스트 상세
- 플랫폼별 발행 결과
- 분석 데이터 (조회수, 좋아요)
- 재발행 / 취소 버튼

---

## 작업 5: 영상 생성

### `/videos`
- 생성된 영상 목록

### `/videos/new`
- 주제 입력
- 모드 선택 (legal, philosophy, senior, news, mystery 등)
- 언어, 포맷, 스타일
- 템플릿 선택 (5개 사전 정의)
- auto_publish 옵션 (생성 후 자동 배포)
- 생성 진행 상황 실시간 표시 (WebSocket 또는 폴링)

---

## 작업 6: 계정 연결

### `/accounts`
- 연결된 소셜 계정 카드 (플랫폼 로고 + 사용자명)
- 새 계정 연결 버튼 (각 플랫폼별)
- OAuth 플로우 → 콜백 처리
- 연결 해제
- 토큰 만료 경고 (빨간 배지)

---

## 작업 7: 분석

### `/analytics`
- 기간 선택 (7d, 30d, 90d)
- 통합 차트:
  - 일별 포스트 수
  - 일별 조회수/좋아요
  - 플랫폼별 비교 (파이 차트)
- TOP 10 포스트 (성과순)
- 성장 추이 (팔로워/구독자)
- 플랫폼별 탭

---

## 작업 8: 웹훅 / API 키 / 설정

### `/webhooks`
- 웹훅 목록
- 추가/수정/삭제
- 전송 이력
- 수동 재전송
- DLQ 보기

### `/api-keys`
- 키 목록 (prefix만 표시)
- 새 키 발급 (모달, 한 번만 노출)
- 회전
- 삭제
- 사용 이력

### `/settings`
- 프로필 (이름, 이메일)
- 비밀번호 변경
- 알림 설정
- 워크스페이스 관리
- 멤버 초대

---

## 작업 9: 결제

### `/billing`
- 현재 플랜 + 다음 결제일
- 사용량 (이번 달)
- 플랜 변경 버튼 → Stripe Checkout
- 결제 이력
- 인보이스 다운로드
- 구독 취소

---

## 작업 10: API 클라이언트

### `dashboard/lib/api-client.ts`
ContentFlow JavaScript SDK 래핑:

```typescript
import { ContentFlow } from 'contentflow-sdk';

export function getClient() {
  const apiKey = getApiKeyFromSession();
  return new ContentFlow({ apiKey, baseUrl: process.env.NEXT_PUBLIC_API_URL });
}
```

모든 페이지는 SWR/TanStack Query로 데이터 페칭.

---

## 작업 11: 환경 변수

### `dashboard/.env.example`
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
```

---

## 작업 12: 빌드 + 배포 설정

- `dashboard/vercel.json` — Vercel 배포 설정
- `npm run build` 통과 확인
- TypeScript strict 모드
- ESLint 통과

---

## 완료 기준

- [ ] Next.js 14 프로젝트 셋업
- [ ] 인증 페이지 (로그인/가입/이메일 인증)
- [ ] 대시보드 홈 (통계 카드 + 최근 활동)
- [ ] 포스트 CRUD 페이지
- [ ] 영상 생성 페이지
- [ ] 계정 연결 페이지 (OAuth 콜백 포함)
- [ ] 분석 페이지 (차트)
- [ ] 웹훅 / API 키 / 설정 페이지
- [ ] 결제 페이지 (Stripe Checkout 연결)
- [ ] ContentFlow SDK 통합
- [ ] 다크모드 + 반응형
- [ ] `npm run build` 통과
- [ ] 백엔드 ruff + pytest 깨지지 않게 확인

---

## 의미

이거 끝나면 ContentFlow가 진짜 SaaS 제품이 된다. 사장님이 사용자 가입 링크 하나 공유하면 그 사람이 대시보드에서 모든 걸 할 수 있게 된다.

지금까지 만든 백엔드 + 18~21개 어댑터 + AI 영상 생성 + 분석이 이 UI 하나로 연결된다. 이게 있어야 진짜로 돈 받고 팔 수 있는 제품이 된다.
