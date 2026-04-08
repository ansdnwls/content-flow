export interface VerticalConfig {
  readonly $schema?: string;
  readonly id: string;
  readonly name: string;
  readonly tagline: string;
  readonly description?: string;
  readonly brand: BrandConfig;
  readonly domain: DomainConfig;
  readonly target: TargetConfig;
  readonly pricing: PricingConfig;
  readonly features: FeaturesConfig;
  readonly landing: LandingConfig;
  readonly dashboard: DashboardConfig;
}

export interface BrandConfig {
  readonly logo?: string;
  readonly favicon?: string;
  readonly colors: ColorConfig;
  readonly font?: FontConfig;
}

export interface ColorConfig {
  readonly primary: string;
  readonly secondary: string;
  readonly accent: string;
  readonly bg: string;
  readonly text: string;
}

export interface FontConfig {
  readonly display: string;
  readonly body: string;
  readonly mono: string;
}

export interface DomainConfig {
  readonly primary: string;
  readonly api?: string;
  readonly docs?: string;
}

export interface TargetConfig {
  readonly persona: string;
  readonly pain_points: readonly string[];
  readonly language: readonly string[];
  readonly region: readonly string[];
}

export interface PricingConfig {
  readonly currency: "USD" | "KRW" | "EUR" | "JPY";
  readonly plans: readonly PlanConfig[];
}

export interface PlanConfig {
  readonly id: string;
  readonly name: string;
  readonly price_monthly: number;
  readonly features: readonly string[];
}

export interface FeaturesConfig {
  readonly core: readonly string[];
  readonly platforms_enabled: readonly string[];
  readonly platforms_hero: readonly string[];
  readonly hide: readonly string[];
}

export interface LandingConfig {
  readonly hero: HeroConfig;
  readonly sections: readonly string[];
}

export interface HeroConfig {
  readonly headline: string;
  readonly sub: string;
  readonly cta_primary: string;
  readonly cta_secondary?: string;
}

export interface DashboardConfig {
  readonly home_widgets: readonly string[];
  readonly nav: readonly string[];
  readonly onboarding_steps: readonly string[];
}

export type SectionType =
  | "hero"
  | "how_it_works"
  | "platforms"
  | "features"
  | "pricing"
  | "testimonials"
  | "faq"
  | "cta_footer";

export const PLATFORM_LABELS: Record<string, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
  instagram: "Instagram",
  x: "X (Twitter)",
  threads: "Threads",
  facebook: "Facebook",
  linkedin: "LinkedIn",
  medium: "Medium",
  naver_blog: "Naver Blog",
  tistory: "Tistory",
  kakao: "Kakao",
  mastodon: "Mastodon",
  line: "LINE",
};

export function formatPrice(amount: number, currency: string): string {
  const formatter = new Intl.NumberFormat(currency === "KRW" ? "ko-KR" : "en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
  });
  return formatter.format(amount);
}

export function loadConfig(configPath: string): VerticalConfig {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require(configPath) as VerticalConfig;
}
