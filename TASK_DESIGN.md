# TASK: ContentFlow 디자인 시스템 + 비주얼 임팩트

> 담당: 디자인팀 (새 인스턴스)
> 우선순위: P0 (랜딩 + 대시보드 동시 적용)

---

## 배경

지금 ContentFlow는 기능은 다 갖춰졌지만 **보는 순간 "와" 소리가 나는 디자인이 없다.** 다른 SaaS와 똑같이 생긴 다크모드 + 그라디언트 액센트 = 흔한 템플릿으로 보인다.

이 작업은 **ContentFlow를 한눈에 기억할 수 있는 브랜드**로 만드는 것이다.

벤치마크: Linear, Vercel, Resend, Cal.com, Raycast — 이 회사들의 공통점은 "한 번 보면 잊혀지지 않는 비주얼 아이덴티티"가 있다는 것.

---

## 시작 전 필수

`/mnt/skills/public/frontend-design/SKILL.md` 파일을 먼저 읽어라.
디자인 토큰, 컴포넌트 패턴, 환경 제약을 다 정리해놨다.

---

## 작업 1: 브랜드 아이덴티티 정의

### 파일: `design/BRAND.md`

ContentFlow의 브랜드를 한 문장으로 정의:

> **"The API for creators who ship"**
> (또는 더 좋은 카피 제안)

### 1.1 컬러 팔레트

다음 3가지 방향 중 하나 선택 (또는 새로 제안):

**Option A: Electric Sunset**
- Primary: `#FF6B35` (electric orange)
- Secondary: `#FFD23F` (sun yellow)
- Accent: `#06FFA5` (mint green)
- Dark BG: `#0A0118` (deep purple-black)
- 정체성: 에너지, 창의성, 크리에이터 친화적

**Option B: Cyber Mono**
- Primary: `#00FF94` (matrix green)
- Secondary: `#0AEFFF` (cyan)
- Accent: `#FF003C` (alert red)
- Dark BG: `#000000` (pure black)
- 정체성: 개발자 친화적, 터미널, 해킹 미학

**Option C: Soft Brutalism**
- Primary: `#FF4D8D` (hot pink)
- Secondary: `#FFCA3A` (warm yellow)
- Accent: `#1982C4` (deep blue)
- Dark BG: `#1A1A2E` (midnight blue)
- 정체성: 친근하지만 강렬한, Notion + Figma 감성

각 옵션의 mood board, 적용 예시, 톤 설명을 작성하고 추천안 1개 제시.

### 1.2 타이포그래피

- **Headline**: 강한 임팩트 폰트 (Inter Display, Söhne, Geist 등)
- **Body**: 가독성 좋은 sans-serif (Inter, Geist)
- **Mono**: 코드 블록용 (JetBrains Mono, Geist Mono)
- 사이즈 스케일 정의 (12, 14, 16, 20, 24, 32, 48, 64, 96)
- 라인 높이, 자간

### 1.3 로고

ContentFlow 로고 SVG 작성:
- 텍스트 로고
- 심볼 (favicon용)
- 다양한 사이즈 + 다크/라이트 버전
- 플랫폼 18~21개를 한 점에서 흩뿌리는 시각적 메타포 활용

---

## 작업 2: 디자인 토큰

### 파일: `design/tokens.css`

CSS 변수로 모든 디자인 토큰 정의:

```css
:root {
  /* Colors */
  --color-primary: ...;
  --color-secondary: ...;
  --color-accent: ...;
  --color-bg: ...;
  --color-bg-elevated: ...;
  --color-text: ...;
  --color-text-muted: ...;
  --color-border: ...;
  
  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  /* ... */
  
  /* Typography */
  --font-display: ...;
  --font-body: ...;
  --font-mono: ...;
  
  /* Shadows */
  --shadow-glow: 0 0 40px var(--color-primary);
  /* ... */
  
  /* Animations */
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  /* ... */
}
```

`landing/`과 `dashboard/` 양쪽에서 import해서 사용.

---

## 작업 3: 랜딩페이지 비주얼 업그레이드

### 파일: `landing/app/page.tsx` 전면 개편

기존 랜딩페이지를 다음 요소로 재구성:

### 3.1 Hero 섹션
- **거대한 타이포그래피** — 화면을 꽉 채우는 헤드라인
- 헤드라인 후보:
  - "One topic. 21 platforms. Zero clicks."
  - "Stop posting. Start shipping."
  - "The unfair API for content."
- 3D 또는 애니메이션 비주얼 (CSS만으로):
  - 중앙에서 21개 플랫폼 로고가 폭발하듯 퍼지는 애니메이션
  - 또는 회전하는 플랫폼 큐브
- 마우스 따라가는 그라디언트 (radial gradient on cursor)

### 3.2 코드 데모 섹션
- 실제 동작하는 것처럼 보이는 코드 블록
- 자동 타이핑 애니메이션
- 코드 → 결과(여러 플랫폼에 게시되는 모습) 시각화
- Python / JS / Go / cURL 탭

### 3.3 18~21개 플랫폼 그리드
- 단순 로고 나열이 아니라 **마우스 호버 시 인터랙션**
- 각 플랫폼 카드가 살짝 떠오르고 색상 변화
- 한국 특화 플랫폼 (네이버, 티스토리, 카카오) 강조 배지

### 3.4 핵심 기능 3개 (피처 카드)
- Content Bomb, Comment Autopilot, Viral Score
- 각 카드에 미니 데모 애니메이션
- 호버 시 더 자세한 정보 펼침

### 3.5 가격표
- 4단 카드 (Free / Build / Scale / Enterprise)
- "Most Popular" 배지
- 호버 시 글로우 효과
- 연간 결제 토글 (월간 ↔ 연간)

### 3.6 소셜 프루프
- "X개의 회사가 사용 중" 카운터
- 실시간 카운트 업 애니메이션 (CountUp)
- 후기 카드 캐러셀

### 3.7 CTA 푸터
- 거대한 "Start free" 버튼
- 카드 필요 없음 강조

---

## 작업 4: 대시보드 비주얼 시스템

### 파일: `dashboard/components/ui/`

shadcn/ui 베이스에 ContentFlow 디자인 토큰 적용:

### 4.1 사이드바
- 글래스모피즘 효과 (`backdrop-filter: blur`)
- 활성 메뉴 항목에 그라디언트 배경
- 아이콘 + 텍스트 + 호버 시 글로우

### 4.2 통계 카드
- 큰 숫자 (display font, 48-64px)
- 작은 변화율 (전월 대비 +12%)
- 미니 스파크라인 차트 내장
- 호버 시 살짝 떠오름

### 4.3 데이터 테이블
- 행 호버 시 부드러운 하이라이트
- 정렬 가능한 헤더
- 페이지네이션 컴포넌트 통일
- 빈 상태 일러스트 (포스트 없을 때)

### 4.4 폼
- floating label 패턴
- 포커스 시 그라디언트 아웃라인
- 에러 상태 강조 (shake 애니메이션)

### 4.5 버튼
- Primary: 그라디언트 + 글로우
- Secondary: 보더만
- Ghost: 호버 시만 배경
- Loading 상태 스피너

---

## 작업 5: 마이크로 인터랙션

### 파일: `dashboard/lib/animations.ts`

**디테일이 차이를 만든다.** 다음 인터랙션 추가:

- 페이지 전환: fade + slide
- 카드 등장: stagger animation (위에서 아래로)
- 버튼 클릭: ripple 효과
- 토스트 알림: 우측 상단에서 슬라이드인
- 스켈레톤 로더: shimmer 애니메이션
- 차트 그리기: 좌→우 드로잉 애니메이션
- 폼 제출 성공: checkmark draw 애니메이션
- 호버: cubic-bezier spring (0.34, 1.56, 0.64, 1)

Framer Motion 사용 가능 (`npm install framer-motion`).

---

## 작업 6: 일러스트레이션 + 이모지

### 파일: `design/illustrations/`

빈 상태, 에러, 온보딩에 사용할 일러스트:

- 빈 포스트 목록 → "아직 포스트가 없어요" + 일러스트
- 빈 분석 → "데이터가 모이는 중이에요"
- 에러 페이지 (404, 500)
- 온보딩 단계별 일러스트

스타일 옵션:
- 옵션 A: 기하학적 미니멀 (Stripe 스타일)
- 옵션 B: 손그림 + 컬러풀 (Notion 스타일)
- 옵션 C: 3D 아이소메트릭 (Linear 스타일)

SVG 또는 Lottie 사용. 외부 라이브러리 (Lucide, Phosphor)도 적극 활용.

---

## 작업 7: 다크모드 + 라이트모드

기본은 다크모드지만 라이트모드도 지원:
- `prefers-color-scheme` 자동 감지
- 사용자 설정 저장
- 모든 토큰이 양쪽에서 동작하는지 확인
- 토글 애니메이션 (해→달)

---

## 작업 8: 모바일 반응형

- 사이드바 → 햄버거 메뉴
- 통계 카드 → 1열 스택
- 테이블 → 카드 형태
- 터치 친화적 (최소 44px 탭 영역)

---

## 작업 9: 접근성

- 모든 인터랙티브 요소에 키보드 포커스
- ARIA 레이블
- 색상만으로 정보 전달 안 하기 (아이콘 + 텍스트 병행)
- 명도 대비 WCAG AA 이상
- prefers-reduced-motion 존중

---

## 작업 10: 디자인 가이드 문서

### 파일: `design/DESIGN_SYSTEM.md`

다음 내용 정리:
- 브랜드 가이드라인
- 컬러 사용 규칙 (어디에 primary, secondary, accent를 쓰나)
- 타이포그래피 스케일
- 컴포넌트 패턴 (버튼, 카드, 폼, 모달)
- Do / Don't 예시
- 스크린샷 갤러리

이 문서가 있어야 미래에 다른 사람이 작업해도 일관성이 유지된다.

---

## 완료 기준

- [ ] `design/BRAND.md` — 브랜드 정의 + 컬러 팔레트 추천
- [ ] `design/tokens.css` — 디자인 토큰
- [ ] 로고 SVG (text + symbol + favicon)
- [ ] `landing/` 전면 개편 — Hero, 코드 데모, 플랫폼 그리드, 가격, CTA
- [ ] `dashboard/` 컴포넌트 디자인 적용 (사이드바, 카드, 테이블, 폼, 버튼)
- [ ] 마이크로 인터랙션 (Framer Motion)
- [ ] 빈 상태 일러스트
- [ ] 다크/라이트 모드
- [ ] 모바일 반응형
- [ ] 접근성 체크
- [ ] `design/DESIGN_SYSTEM.md` — 가이드 문서
- [ ] `landing/` + `dashboard/` 빌드 통과

---

## 영감 (Reference)

다음 사이트들의 디자인을 참고해라:

| 사이트 | 배울 점 |
|--------|--------|
| linear.app | 타이포그래피, 디테일, 모션 |
| vercel.com | 다크모드 그라디언트, 코드 데모 |
| resend.com | API 회사 랜딩의 정석 |
| cal.com | 친근한 다크모드, 일러스트 |
| raycast.com | 임팩트 있는 헤드라인, 비주얼 |
| supabase.com | 개발자 친화적 + 시각적 임팩트 |

이들의 공통점:
1. **거대한 타이포그래피** (페이지를 압도하는 헤드라인)
2. **인터랙티브 비주얼** (마우스 따라가는 그라디언트, 호버 효과)
3. **코드를 시적으로 보여주기** (코드 자체가 디자인 요소)
4. **여백을 두려워하지 않음** (sparse layout)
5. **마이크로 카피의 위트** (버튼 텍스트조차 재미있음)

---

## 가장 중요한 것

**"흔한 SaaS"가 아니라 "한 번 보면 잊혀지지 않는 제품"으로 만들어라.**

흔한 다크모드 + 보라색 그라디언트는 절대 금지. 그건 5,000개 SaaS가 다 하고 있다.

ContentFlow만의 시그니처 비주얼을 만들어라. 사람들이 "아, ContentFlow!" 하고 바로 알아볼 수 있는 무언가가 필요하다.

겁먹지 말고 과감하게 가라.
