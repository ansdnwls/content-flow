# TASK: Vertical Launcher — 버티컬 제품 템플릿 시스템

> 담당: 코드3
> 우선순위: P0 (ContentFlow 확장의 핵심 기반)

---

## 배경

ContentFlow는 "모두를 위한 SaaS"로 만들면 경쟁에서 이기기 어렵다. 대신 **특정 직군에 완벽하게 맞춘 버티컬 제품 여러 개**를 빠르게 찍어내는 전략으로 간다.

같은 ContentFlow 엔진(21개 어댑터, AI 영상, 결제, 대시보드) 위에:
- **YtBoost** — 유튜버 증폭기
- **ShopSync** — 쇼핑몰 셀러
- **DongneBiz** — 동네 사장 (네이버 플레이스 특화)
- **EstateHub** — 공인중개사
- **LetterBoom** — 뉴스레터 확산기

5개를 각각 따로 개발하면 5배 시간이 든다. 대신 **Vertical Launcher**라는 템플릿 시스템을 만들어서 **30분 만에 새 버티컬을 찍어낼 수 있게** 한다.

사장님이 말한 프레임워크 전략의 완성형이다: `com`(ContentFlow 엔진)은 공유하고, `biz`(버티컬별 UI/브랜드/특화 기능)만 다르게.

---

## 목표

```bash
pnpm create vertical ytboost
# → verticals/ytboost/ 디렉토리 생성
# → landing + dashboard + config + presets 자동 생성
# → 브랜드/컬러/가격만 바꾸면 30분 안에 새 제품 런칭 가능
```

---

## 작업 1: 디렉토리 구조 설계

### 전체 레포 구조

```
content-flow/
├── app/                     # ContentFlow API (공유 com)
├── dashboard/               # ContentFlow 본체 대시보드
├── landing/                 # ContentFlow 본체 랜딩
├── sdk/                     # SDK (공유)
├── docs-site/               # 문서 사이트
│
├── verticals/               # ★ 버티컬 제품들 (biz)
│   ├── _template/           # 템플릿 원본
│   │   ├── config.json
│   │   ├── landing/
│   │   ├── dashboard/
│   │   ├── presets/
│   │   └── README.md
│   ├── ytboost/             # 유튜버 증폭기
│   ├── shopsync/            # 쇼핑몰 셀러
│   └── ...
│
├── packages/                # 공유 패키지
│   ├── cf-engine/           # ContentFlow JS SDK 래퍼
│   ├── cf-ui/               # 공유 UI 컴포넌트
│   └── cf-config/           # 공유 설정 타입
│
└── tools/
    └── create-vertical/     # CLI 도구
```

---

## 작업 2: config.json 스키마

### 파일: `verticals/_template/config.json`

각 버티컬은 이 파일 하나로 정의된다:

```json
{
  "$schema": "../../packages/cf-config/schema.json",
  "id": "ytboost",
  "name": "YtBoost",
  "tagline": "Turn 1 YouTube video into 18 pieces of content",
  "description": "유튜버를 위한 자동 증폭 도구. 유튜브 영상 하나만 올리면 쇼츠, 인스타 릴스, 틱톡, 트위터 스레드까지 자동 배포.",
  
  "brand": {
    "logo": "./assets/logo.svg",
    "favicon": "./assets/favicon.ico",
    "colors": {
      "primary": "#FF0000",
      "secondary": "#282828",
      "accent": "#00D4AA",
      "bg": "#0F0F0F",
      "text": "#FFFFFF"
    },
    "font": {
      "display": "Inter Display",
      "body": "Inter",
      "mono": "JetBrains Mono"
    }
  },
  
  "domain": {
    "primary": "ytboost.dev",
    "api": "api.ytboost.dev",
    "docs": "docs.ytboost.dev"
  },
  
  "target": {
    "persona": "YouTube creators with 1K-100K subscribers",
    "pain_points": [
      "Shooting one video takes hours, posting it everywhere takes more",
      "Need shorts for multiple platforms",
      "Can't manually manage comments on 5 platforms"
    ],
    "language": ["en", "ko"],
    "region": ["US", "KR", "global"]
  },
  
  "pricing": {
    "currency": "USD",
    "plans": [
      {
        "id": "starter",
        "name": "Starter",
        "price_monthly": 0,
        "features": ["1 YouTube channel", "Auto shorts from 1 video/mo", "3 platforms"]
      },
      {
        "id": "creator",
        "name": "Creator",
        "price_monthly": 29,
        "features": ["3 YouTube channels", "Unlimited auto shorts", "All 18 platforms", "Comment autopilot"]
      },
      {
        "id": "studio",
        "name": "Studio",
        "price_monthly": 99,
        "features": ["Unlimited channels", "AI video generation", "Viral score", "White-label"]
      }
    ]
  },
  
  "features": {
    "core": [
      "youtube_upload_trigger",
      "auto_shorts_extraction",
      "multi_platform_distribution",
      "comment_autopilot"
    ],
    "platforms_enabled": [
      "youtube", "tiktok", "instagram", "x", "threads", "facebook"
    ],
    "platforms_hero": [
      "youtube", "tiktok", "instagram"
    ],
    "hide": [
      "naver_blog", "tistory", "kakao"
    ]
  },
  
  "landing": {
    "hero": {
      "headline": "Upload once. Ship everywhere.",
      "sub": "Your YouTube video becomes 18 pieces of content automatically.",
      "cta_primary": "Start free",
      "cta_secondary": "Watch demo"
    },
    "sections": [
      "hero",
      "how_it_works",
      "platforms",
      "features",
      "pricing",
      "testimonials",
      "faq",
      "cta_footer"
    ]
  },
  
  "dashboard": {
    "home_widgets": [
      "youtube_channel_stats",
      "recent_shorts_generated",
      "distribution_map",
      "viral_score_trending"
    ],
    "nav": [
      "home",
      "videos",
      "shorts",
      "distribution",
      "comments",
      "analytics",
      "settings"
    ],
    "onboarding_steps": [
      "connect_youtube",
      "connect_2nd_platform",
      "set_auto_distribution",
      "first_upload_trigger"
    ]
  }
}
```

---

## 작업 3: CLI 도구

### 파일: `tools/create-vertical/`

```bash
pnpm create vertical ytboost
# 또는
npx create-vertical ytboost
```

### 기능

1. `verticals/_template/`을 `verticals/<name>/`으로 복사
2. 대화형 프롬프트:
   - Vertical 이름 (예: YtBoost)
   - 태그라인
   - 브랜드 컬러 (primary)
   - 타겟 고객 (한 줄)
   - 주력 플랫폼 선택 (체크박스)
   - 기본 가격 (무료/유료)
3. `config.json` 자동 생성
4. `package.json`의 name 필드 업데이트
5. 도메인 placeholder 설정
6. 최초 commit 준비

### 파일: `tools/create-vertical/index.ts`

```typescript
import { intro, outro, text, select, multiselect } from '@clack/prompts';
import { writeFileSync, cpSync } from 'fs';
import path from 'path';

async function main() {
  intro('🚀 Create a new ContentFlow vertical');
  
  const name = await text({
    message: 'Vertical ID (lowercase, no spaces)',
    placeholder: 'ytboost',
    validate: (v) => /^[a-z][a-z0-9-]*$/.test(v) ? undefined : 'Invalid format',
  });
  
  const displayName = await text({ message: 'Display name', placeholder: 'YtBoost' });
  const tagline = await text({ message: 'Tagline (one line)' });
  const primaryColor = await text({ message: 'Primary color (hex)', placeholder: '#FF0000' });
  
  const platforms = await multiselect({
    message: 'Hero platforms (shown prominently)',
    options: [
      { value: 'youtube', label: 'YouTube' },
      { value: 'tiktok', label: 'TikTok' },
      { value: 'instagram', label: 'Instagram' },
      // ... 21개
    ],
  });
  
  // Copy template
  const targetDir = path.join('verticals', name as string);
  cpSync('verticals/_template', targetDir, { recursive: true });
  
  // Update config.json
  const config = JSON.parse(readFileSync(`${targetDir}/config.json`, 'utf-8'));
  config.id = name;
  config.name = displayName;
  config.tagline = tagline;
  config.brand.colors.primary = primaryColor;
  config.features.platforms_hero = platforms;
  writeFileSync(`${targetDir}/config.json`, JSON.stringify(config, null, 2));
  
  outro(`✅ Created verticals/${name}. Run: cd verticals/${name} && pnpm dev`);
}

main();
```

---

## 작업 4: 템플릿 랜딩페이지

### 파일: `verticals/_template/landing/`

Next.js 14 기반, `config.json`을 읽어서 자동 렌더링:

```typescript
// verticals/_template/landing/app/page.tsx
import config from '../config.json';
import { Hero, Platforms, Pricing, FAQ } from '@/components';

export default function Landing() {
  return (
    <>
      <Hero 
        headline={config.landing.hero.headline}
        sub={config.landing.hero.sub}
        cta={config.landing.hero.cta_primary}
      />
      <Platforms list={config.features.platforms_hero} />
      <Pricing plans={config.pricing.plans} />
      <FAQ />
    </>
  );
}
```

### 공유 컴포넌트: `packages/cf-ui/`

본체 `landing/`에서 쓴 컴포넌트들을 패키지로 분리:
- Hero
- PlatformGrid
- PricingTable
- FAQ
- Footer
- CodeDemo

모든 버티컬이 같은 컴포넌트를 쓰되 config로 커스터마이즈.

### 테마 시스템

`config.brand.colors`를 CSS 변수로 자동 주입:

```typescript
// verticals/_template/landing/app/layout.tsx
import config from '../config.json';

export default function RootLayout({ children }) {
  return (
    <html>
      <head>
        <style>{`
          :root {
            --color-primary: ${config.brand.colors.primary};
            --color-secondary: ${config.brand.colors.secondary};
            --color-accent: ${config.brand.colors.accent};
            --color-bg: ${config.brand.colors.bg};
          }
        `}</style>
      </head>
      <body>{children}</body>
    </html>
  );
}
```

---

## 작업 5: 템플릿 대시보드

### 파일: `verticals/_template/dashboard/`

본체 `dashboard/`를 기반으로 하되:

1. **네비게이션이 config 기반**
```typescript
// verticals/_template/dashboard/components/sidebar.tsx
import config from '../../config.json';

const navItems = config.dashboard.nav.map(key => NAV_MAP[key]);
```

2. **홈 위젯이 config 기반**
```typescript
const widgets = config.dashboard.home_widgets.map(key => WIDGET_MAP[key]);
```

3. **숨겨야 할 기능은 config.features.hide 참고**
```typescript
if (!config.features.hide.includes('videos')) {
  // Videos 메뉴 표시
}
```

### 위젯 라이브러리: `packages/cf-ui/widgets/`

각 위젯을 독립 컴포넌트로:
- `YouTubeChannelStats` — ytboost용
- `ShopSyncInventoryCard` — shopsync용
- `DistributionMap` — 공통
- `ViralScoreTrending` — 공통

버티컬 특화 위젯은 `verticals/<name>/widgets/`에 별도 추가 가능.

---

## 작업 6: Presets (플랫폼 프리셋)

### 파일: `verticals/_template/presets/`

각 버티컬마다 어떤 플랫폼 조합이 기본인지:

```json
// verticals/ytboost/presets/creator_workflow.json
{
  "id": "creator_workflow",
  "name": "Full Creator Workflow",
  "description": "YouTube 업로드 → 쇼츠 자동 생성 → 6개 플랫폼 배포",
  "trigger": {
    "type": "youtube_upload",
    "channel_ids": []
  },
  "pipeline": [
    {
      "step": "extract_shorts",
      "count": 3,
      "duration": 60
    },
    {
      "step": "distribute",
      "platforms": ["youtube_shorts", "tiktok", "instagram_reels"]
    },
    {
      "step": "comment_autopilot",
      "tone": "friendly",
      "auto_approve": false
    }
  ]
}
```

사용자가 버티컬 온보딩 때 이 preset을 선택하면 기본 설정이 자동 구성.

---

## 작업 7: 배포 파이프라인

각 버티컬을 독립 배포 가능하게:

### 파일: `verticals/<name>/vercel.json`

```json
{
  "name": "ytboost",
  "builds": [
    { "src": "landing/package.json", "use": "@vercel/next" },
    { "src": "dashboard/package.json", "use": "@vercel/next" }
  ],
  "routes": [
    { "src": "/app/(.*)", "dest": "/dashboard/$1" },
    { "src": "/(.*)", "dest": "/landing/$1" }
  ]
}
```

### GitHub Actions

### 파일: `.github/workflows/deploy-vertical.yml`

```yaml
name: Deploy Vertical

on:
  push:
    paths:
      - 'verticals/**'

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      verticals: ${{ steps.changes.outputs.verticals }}
    steps:
      - uses: dorny/paths-filter@v3
        id: changes
        with:
          filters: |
            ytboost: 'verticals/ytboost/**'
            shopsync: 'verticals/shopsync/**'
  
  deploy:
    needs: detect-changes
    strategy:
      matrix:
        vertical: ${{ fromJson(needs.detect-changes.outputs.verticals) }}
    steps:
      - name: Deploy to Vercel
        run: vercel deploy --prod --scope ${{ matrix.vertical }}
```

변경된 버티컬만 재배포.

---

## 작업 8: 첫 번째 버티컬 — YtBoost (유튜버 증폭기)

템플릿 만들고 바로 검증용으로 첫 번째 버티컬 생성:

```bash
pnpm create vertical ytboost
```

### verticals/ytboost/config.json 작성

- 브랜드: 유튜브 레드(#FF0000) 기반
- 타겟: 1K~100K 구독자 유튜버
- 가격: $0 / $29 / $99
- 주력 플랫폼: YouTube, TikTok, Instagram, X, Threads, Facebook
- 특화 기능:
  - `youtube_upload_trigger` — 유튜브 업로드 webhook 자동 감지
  - `auto_shorts_extraction` — AI가 훅 구간 찾아서 쇼츠 3개 추출
  - `comment_autopilot_youtube` — 댓글 자동 답변

### verticals/ytboost/landing/ 커스터마이즈

- 헤로 헤드라인: "Upload once. Ship everywhere."
- 데모 영상 임베드
- 유튜버 후기 (placeholder)

### verticals/ytboost/dashboard/ 커스터마이즈

- 홈 위젯: 연결된 유튜브 채널 통계
- 네비: Videos, Shorts, Distribution, Comments
- 온보딩: 유튜브 연결 → 추가 플랫폼 → 자동 배포 설정

### 빌드 + 배포 검증

- `cd verticals/ytboost && pnpm install && pnpm build`
- Vercel 프리뷰 배포
- 스크린샷 → `verticals/ytboost/README.md`

---

## 작업 9: 두 번째 버티컬 — ShopSync (쇼핑몰 셀러)

첫 버티컬이 잘 되면 두 번째도:

```bash
pnpm create vertical shopsync
```

### verticals/shopsync/config.json

- 브랜드: 오렌지/옐로(쇼핑 느낌)
- 타겟: 네이버 스마트스토어 + 쿠팡 + 11번가 셀러
- 가격: ₩0 / ₩49,000 / ₩99,000 (원화!)
- 주력 플랫폼: 인스타, 페이스북, 네이버 블로그, 티스토리, 카카오
- 특화 기능:
  - `product_to_copy` — 상품 이미지 → AI 상세페이지 자동 생성
  - `inventory_sync` — 재고 임박 알림 자동 포스팅
  - `price_change_notifier` — 가격 변동 시 전 플랫폼 동기화

---

## 작업 10: 문서화

### 파일: `docs/VERTICAL_GUIDE.md`

버티컬 제품 만드는 법:

1. `pnpm create vertical <name>` 실행
2. `config.json` 채우기 (브랜드, 가격, 기능)
3. 특화 위젯 필요하면 `verticals/<name>/widgets/`에 추가
4. 랜딩페이지 섹션 커스터마이즈 (`verticals/<name>/landing/app/`)
5. 로컬 테스트 (`pnpm dev`)
6. 배포 (`git push → GitHub Actions 자동 배포`)

예상 소요 시간: **30분~2시간** (커스터마이즈 범위에 따라)

### 파일: `verticals/README.md`

현재 만들어진 버티컬 목록과 각각의 상태:

| Vertical | Status | Domain | Target |
|----------|--------|--------|--------|
| ytboost | 🟢 Live | ytboost.dev | YouTubers |
| shopsync | 🟡 Beta | shopsync.kr | Ecommerce sellers |
| ... | ... | ... | ... |

---

## 완료 기준

- [ ] `verticals/_template/` 완성 (landing + dashboard + config.json + presets)
- [ ] `packages/cf-ui/` 공유 컴포넌트 라이브러리
- [ ] `tools/create-vertical/` CLI 도구
- [ ] `pnpm create vertical <name>` 동작 확인
- [ ] 첫 번째 버티컬: `verticals/ytboost/` 생성 + 빌드
- [ ] 두 번째 버티컬: `verticals/shopsync/` 생성 + 빌드
- [ ] `.github/workflows/deploy-vertical.yml` 변경 감지 배포
- [ ] `docs/VERTICAL_GUIDE.md` 가이드
- [ ] 본체 ruff + pytest 깨지지 않게 확인
- [ ] `verticals/ytboost`, `verticals/shopsync` 각각 `pnpm build` 통과

---

## 의미

이 작업이 끝나면 ContentFlow는 **제품 1개**가 아니라 **제품을 찍어내는 공장**이 된다.

```
Before:
- ContentFlow 하나 운영
- 새 시장 들어가려면 처음부터 다시

After:
- `pnpm create vertical <name>` 한 줄
- 30분 만에 새 버티컬 런칭
- 같은 ContentFlow 엔진 재사용
- 유지보수는 본체만, 버티컬은 config만
```

사장님이 2주 전에 말한 **"안정된 프레임워크를 포크해서 새 프로젝트 찍어내는 전략"**의 완성형이다.

이게 있으면:
1. **YtBoost** 런칭 → 실사용 데이터 수집
2. **ShopSync** 런칭 → 다른 시장 검증
3. 데이터 보고 잘 되는 쪽에 집중
4. 안 되는 버티컬은 아카이브 (비용 거의 없음)
5. 새 아이디어 생기면 30분 안에 테스트

**ContentFlow의 진짜 해자는 기능이 아니라 이 Vertical Launcher다.** 경쟁사가 제품 1개 만들 동안 우리는 5개, 10개를 찍어낼 수 있다.
