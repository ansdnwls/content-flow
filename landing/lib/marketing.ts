export type MarketingPlatform = {
  id: string;
  label: string;
  short: string;
  color: string;
  category: string;
};

export const marketingPlatforms: MarketingPlatform[] = [
  { id: "youtube", label: "YouTube", short: "YT", color: "#ff6b35", category: "video" },
  { id: "tiktok", label: "TikTok", short: "TT", color: "#ffd23f", category: "video" },
  { id: "instagram", label: "Instagram", short: "IG", color: "#ff8f6a", category: "social" },
  { id: "x", label: "X", short: "X", color: "#fff6ef", category: "social" },
  { id: "linkedin", label: "LinkedIn", short: "IN", color: "#06ffa5", category: "social" },
  { id: "facebook", label: "Facebook", short: "FB", color: "#ffd23f", category: "social" },
  { id: "threads", label: "Threads", short: "TH", color: "#fff6ef", category: "social" },
  { id: "pinterest", label: "Pinterest", short: "PT", color: "#ff6f7d", category: "social" },
  { id: "reddit", label: "Reddit", short: "RD", color: "#ff8f6a", category: "community" },
  { id: "bluesky", label: "Bluesky", short: "BS", color: "#8cd7ff", category: "social" },
  { id: "snapchat", label: "Snapchat", short: "SC", color: "#ffd23f", category: "social" },
  { id: "telegram", label: "Telegram", short: "TG", color: "#6ff7ff", category: "community" },
  { id: "wordpress", label: "WordPress", short: "WP", color: "#efe0d6", category: "blog" },
  { id: "google-business", label: "Google Business", short: "GB", color: "#06ffa5", category: "local" },
  { id: "naver-blog", label: "Naver Blog", short: "NB", color: "#06ffa5", category: "korea" },
  { id: "tistory", label: "Tistory", short: "TS", color: "#ff6b35", category: "korea" },
  { id: "kakao", label: "Kakao", short: "KK", color: "#ffd23f", category: "korea" },
  { id: "note", label: "note.com", short: "NO", color: "#fff6ef", category: "japan" },
  { id: "line", label: "LINE", short: "LN", color: "#06ffa5", category: "japan" },
  { id: "mastodon", label: "Mastodon", short: "MD", color: "#ff9cdb", category: "community" },
  { id: "medium", label: "Medium", short: "ME", color: "#fff6ef", category: "blog" },
];

export const useCases = [
  {
    slug: "indie-creators",
    title: "Publish one video everywhere without becoming a full-time operator.",
    shortTitle: "Indie Creators",
    persona: "Solo creator",
    kicker: "YouTube in. Eighteen channels out.",
    description:
      "ContentFlow takes a single video idea and turns it into a cross-platform launch burst with channel-native copy, thumbnails, and reply handling.",
    highlightPlan: "Build",
    codeExample: "client.bombs.create({ topic: 'weekly creator update', platforms: ['youtube', 'instagram', 'threads'] })",
    cta: "Start with Build",
  },
  {
    slug: "marketing-agencies",
    title: "Run ten clients like you hired an invisible ops team.",
    shortTitle: "Marketing Agencies",
    persona: "Agency operator",
    kicker: "Ten channels. One operator.",
    description:
      "Agencies use ContentFlow to standardize production handoff, automate distribution, and keep comment workflows moving without adding overhead.",
    highlightPlan: "Scale",
    codeExample: "client.posts.create({ workspace: 'acme', text: 'launch day', platforms: ['linkedin', 'x_twitter', 'facebook'] })",
    cta: "Talk to sales",
  },
  {
    slug: "saas-builders",
    title: "Turn months of social integrations into one afternoon.",
    shortTitle: "SaaS Builders",
    persona: "Developer-first product team",
    kicker: "Ship the integrations. Keep your roadmap.",
    description:
      "Use the API and SDKs to add publish, video, analytics, and reply flows without building and maintaining every platform adapter yourself.",
    highlightPlan: "Enterprise",
    codeExample: "await client.videos.generate({ topic: 'release notes', auto_publish: { enabled: true, platforms: ['youtube', 'linkedin'] } })",
    cta: "Read the API docs",
  },
  {
    slug: "korean-businesses",
    title: "네이버, 티스토리, 카카오까지 한 번에 보냅니다.",
    shortTitle: "한국 사장님",
    persona: "Korean business owner",
    kicker: "국내용 채널도 예외 없이 자동화.",
    description:
      "글로벌 툴이 자주 놓치는 네이버 블로그, 티스토리, 카카오, LINE 같은 지역 채널까지 같은 워크플로우에서 다룹니다.",
    highlightPlan: "Build",
    codeExample: "client.posts.create({ text: '신제품 공지', platforms: ['naver_blog', 'tistory', 'kakao'] })",
    cta: "무료로 시작하기",
  },
] as const;

export const productHunt = {
  tagline: "1 API. 21 platforms. 0 clicks.",
  alternatives: ["Stop posting. Start shipping.", "Content distribution on autopilot"],
  description: `# ContentFlow\n\nContentFlow turns one topic into a full publishing burst.\n\n## What it does\n- Pushes one brief into 21 platform-ready outputs\n- Generates video jobs and routes them into publishing flows\n- Keeps comments moving with Autopilot reply drafts\n\n## Why now\nCreators and growth teams are still stitching together brittle scripts, schedulers, and inbox tools. ContentFlow gives them one operational layer instead.\n\n## Demo\n- Launch burst demo: /marketing/demos/demo-storyboard.md\n- Gallery masters: /marketing/product-hunt\n\nIf you build, publish, or operate content at scale, this is for you.`,
} as const;
