export type Token = {
  value: string;
  kind?: "plain" | "keyword" | "string" | "func" | "comment" | "type" | "property" | "number";
};

export type CodeLine = Token[];

export type Platform = {
  name: string;
  glyph: string;
  color: string;
  category: string;
  badge?: string;
};

export const platforms = [
  { name: "YouTube", glyph: "YT", color: "#ff6b35", category: "video" },
  { name: "TikTok", glyph: "TT", color: "#ffd23f", category: "video" },
  { name: "Instagram", glyph: "IG", color: "#ff8f6a", category: "social" },
  { name: "X", glyph: "X", color: "#fff6ef", category: "social" },
  { name: "LinkedIn", glyph: "IN", color: "#06ffa5", category: "social" },
  { name: "Facebook", glyph: "FB", color: "#ffd23f", category: "social" },
  { name: "Threads", glyph: "TH", color: "#fff6ef", category: "social" },
  { name: "Pinterest", glyph: "PT", color: "#ff6f7d", category: "social" },
  { name: "Reddit", glyph: "RD", color: "#ff8f6a", category: "community" },
  { name: "Bluesky", glyph: "BS", color: "#8cd7ff", category: "social" },
  { name: "Snapchat", glyph: "SC", color: "#ffd23f", category: "social" },
  { name: "Telegram", glyph: "TG", color: "#6ff7ff", category: "community" },
  { name: "WordPress", glyph: "WP", color: "#efe0d6", category: "blog" },
  { name: "Google Business", glyph: "GB", color: "#06ffa5", category: "local" },
  { name: "Naver Blog", glyph: "NB", color: "#06ffa5", category: "korea", badge: "KR" },
  { name: "Tistory", glyph: "TS", color: "#ff6b35", category: "korea", badge: "KR" },
  { name: "Kakao", glyph: "KK", color: "#ffd23f", category: "korea", badge: "KR" },
  { name: "note.com", glyph: "NO", color: "#fff6ef", category: "japan", badge: "JP" },
  { name: "LINE", glyph: "LN", color: "#06ffa5", category: "japan", badge: "JP" },
  { name: "Mastodon", glyph: "MD", color: "#ff9cdb", category: "community" },
  { name: "Medium", glyph: "ME", color: "#fff6ef", category: "blog" },
] as const satisfies readonly Platform[];

export const featureCards = [
  {
    eyebrow: "Content Bomb",
    title: "Detonate one brief into a full campaign matrix.",
    description:
      "Split one idea into platform-native hooks, post bodies, carousel beats, blog outlines, and thumbnail prompts in a single pass.",
    bullet: "21 outputs spin up from one input without copy-paste ops.",
    stat: "4.3x faster launch cycles",
  },
  {
    eyebrow: "Comment Autopilot",
    title: "Keep every channel responsive without staffing a war room.",
    description:
      "Collect cross-platform replies, classify intent, and draft brand-safe responses before conversations cool off.",
    bullet: "Operators stay in control while the queue keeps moving.",
    stat: "92% response coverage",
  },
  {
    eyebrow: "Viral Score",
    title: "Rank ideas before production money gets burned.",
    description:
      "Model packaging quality, hook strength, spread potential, and regional fit so the team only produces what has leverage.",
    bullet: "Greenlight topics with signal, not gut feel.",
    stat: "+27% average lift",
  },
] as const;

export const pricingPlans = [
  {
    name: "Free",
    monthly: 0,
    yearly: 0,
    cadence: "/month",
    highlight: false,
    description: "For testing the API shape and validating your first publishing burst.",
    features: ["20 posts / month", "3 AI videos / month", "2 platform bundles", "Docs + SDK access"],
  },
  {
    name: "Build",
    monthly: 39,
    yearly: 31,
    cadence: "/month",
    highlight: true,
    description: "For solo operators and compact teams who need distribution leverage every week.",
    features: ["240 posts / month", "20 AI videos / month", "Content Bomb", "Comment Autopilot"],
  },
  {
    name: "Scale",
    monthly: 129,
    yearly: 99,
    cadence: "/month",
    highlight: false,
    description: "For brands and agencies running multiple content lanes with real volume targets.",
    features: ["Unlimited posts", "100 AI videos / month", "Regional platform coverage", "Advanced analytics"],
  },
  {
    name: "Enterprise",
    monthly: null,
    yearly: null,
    cadence: "",
    highlight: false,
    description: "For media ops, internal growth teams, and partners with governance or SLA requirements.",
    features: ["Custom limits", "Private onboarding", "Dedicated roadmap channel", "Custom compliance controls"],
  },
] as const;

export const testimonials = [
  {
    quote:
      "We stopped treating cross-platform publishing like a checklist. ContentFlow turned it into one motion system.",
    name: "Jiwoo Park",
    role: "Head of Content, Daybreak Studio",
  },
  {
    quote:
      "The Korea and Japan endpoints mattered. Every generic scheduler looked global until we hit the actual channel mix.",
    name: "Mina Chen",
    role: "Growth Ops, Horizon Commerce",
  },
  {
    quote:
      "Comment Autopilot took the most fragile part of our workflow and made it operational instead of reactive.",
    name: "Alex Morgan",
    role: "Audience Lead, North Signal",
  },
] as const;

export const faqs = [
  {
    question: "Is this just a scheduler with nicer branding?",
    answer:
      "No. The model is orchestration, not calendar management. ContentFlow handles generation, distribution, and reply operations in one system.",
  },
  {
    question: "Can we start with one platform and expand later?",
    answer:
      "Yes. Most teams begin with two or three core channels, then expand once the distribution playbook is stable.",
  },
  {
    question: "Why highlight Korea and Japan-specific platforms?",
    answer:
      "Because that is where generic global tooling usually breaks. ContentFlow treats regional coverage as a first-class feature, not an afterthought.",
  },
  {
    question: "How does video generation connect to publishing?",
    answer:
      "Video jobs can feed directly into a publish workflow so the output URL, metadata, and posting instructions move as one unit.",
  },
  {
    question: "How should this site be deployed?",
    answer:
      "Deploy `landing/` as the public Vercel project root and keep the API where it already lives. The docs and product story then share one domain.",
  },
] as const;

export const socialProofStats = [
  { label: "teams shipping weekly", value: 184 },
  { label: "platform actions per day", value: 12840 },
  { label: "avg. minutes saved per launch", value: 73 },
] as const;

export const proofLogos = ["North Signal", "Aster Media", "Studio Layer", "Sonic Draft", "Motive", "Orbit House"] as const;

export const navLinks = [
  { href: "/#platforms", label: "Platforms" },
  { href: "/#features", label: "Signal" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
] as const;

export const endpointGroups = [
  {
    title: "Posts API",
    description: "Immediate publish, scheduling, status lookups, and cancellation.",
    endpoints: ["POST /api/v1/posts", "GET /api/v1/posts", "GET /api/v1/posts/{id}", "DELETE /api/v1/posts/{id}"],
  },
  {
    title: "Videos API",
    description: "Generate through yt-factory, track status, and trigger auto-publish flows.",
    endpoints: ["POST /api/v1/videos/generate", "GET /api/v1/videos/{id}"],
  },
  {
    title: "Accounts API",
    description: "OAuth connect flows and connected account inventory.",
    endpoints: ["POST /api/v1/accounts/connect/{platform}", "GET /api/v1/accounts", "DELETE /api/v1/accounts/{id}"],
  },
  {
    title: "Signals",
    description: "Analytics, bombs, comments, and webhook delivery hooks.",
    endpoints: ["GET /api/v1/analytics", "POST /api/v1/bombs", "POST /api/v1/comments/collect", "POST /api/v1/webhooks"],
  },
] as const;

export const pythonSnippet: CodeLine[] = [
  [{ value: "from", kind: "keyword" }, { value: " " }, { value: "contentflow", kind: "string" }, { value: " " }, { value: "import", kind: "keyword" }, { value: " " }, { value: "ContentFlow", kind: "type" }],
  [],
  [{ value: "client" }, { value: " = " }, { value: "ContentFlow", kind: "type" }, { value: "(" }, { value: "api_key", kind: "property" }, { value: "=" }, { value: '"cf_live_..."', kind: "string" }, { value: ")" }],
  [],
  [{ value: "burst" }, { value: " = " }, { value: "client" }, { value: "." }, { value: "bombs", kind: "property" }, { value: "." }, { value: "create", kind: "func" }, { value: "(" }],
  [{ value: "    " }, { value: "topic", kind: "property" }, { value: "=" }, { value: '"2026 short-form trends"', kind: "string" }, { value: "," }],
  [{ value: "    " }, { value: "platforms", kind: "property" }, { value: "=" }, { value: '["youtube", "tiktok", "naver_blog"]', kind: "string" }, { value: "," }],
  [{ value: "    " }, { value: "voice", kind: "property" }, { value: "=" }, { value: '"direct"', kind: "string" }, { value: "," }],
  [{ value: ")" }],
];

export const javascriptSnippet: CodeLine[] = [
  [{ value: "import", kind: "keyword" }, { value: " " }, { value: "{ ContentFlow }", kind: "type" }, { value: " " }, { value: "from", kind: "keyword" }, { value: " " }, { value: '"@contentflow/sdk"', kind: "string" }],
  [],
  [{ value: "const", kind: "keyword" }, { value: " burst = await " }, { value: "client.bombs.", kind: "property" }, { value: "create", kind: "func" }, { value: "(" }, { value: "{" }],
  [{ value: '  topic: "Ship once. Publish everywhere.",', kind: "string" }],
  [{ value: '  platforms: ["youtube", "instagram", "threads"],', kind: "string" }],
  [{ value: '  replyPolicy: "autopilot",', kind: "string" }],
  [{ value: '  locale: "ko-KR"', kind: "string" }],
  [{ value: "});" }],
];

export const goSnippet: CodeLine[] = [
  [{ value: "client", kind: "keyword" }, { value: " := " }, { value: "contentflow.", kind: "property" }, { value: "NewClient", kind: "func" }, { value: `("cf_live_...")`, kind: "string" }],
  [],
  [{ value: "req", kind: "keyword" }, { value: " := " }, { value: "contentflow.", kind: "property" }, { value: "CreatePostRequest", kind: "type" }, { value: "{" }],
  [{ value: "  " }, { value: 'Text: "Launch this across KR + global channels",', kind: "string" }],
  [{ value: "  " }, { value: 'Platforms: []string{"x_twitter", "kakao", "line"},', kind: "string" }],
  [{ value: "}" }],
  [],
  [{ value: "post", kind: "keyword" }, { value: ", " }, { value: "err", kind: "keyword" }, { value: " := client." }, { value: "Posts", kind: "property" }, { value: "." }, { value: "Create", kind: "func" }, { value: "(ctx, req)" }],
];

export const curlSnippet: CodeLine[] = [
  [{ value: "curl", kind: "func" }, { value: " -X POST https://api.contentflow.sh/api/v1/posts" }],
  [{ value: '  -H "Content-Type: application/json"', kind: "string" }],
  [{ value: '  -H "X-API-Key: cf_live_replace_me"', kind: "string" }],
  [{ value: "  -d '{", kind: "string" }],
  [{ value: '    "text": "Launch post",', kind: "string" }],
  [{ value: '    "platforms": ["youtube", "kakao", "line"],', kind: "string" }],
  [{ value: '    "media_urls": ["https://cdn.example.com/video.mp4"]', kind: "string" }],
  [{ value: "  }'", kind: "string" }],
];
