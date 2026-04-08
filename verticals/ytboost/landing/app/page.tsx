import config from "../../config.json";
import { Hero } from "@contentflow/ui/components";
import { PlatformGrid } from "@contentflow/ui/components";
import { PricingTable } from "@contentflow/ui/components";
import { HowItWorks } from "@contentflow/ui/components";
import { FAQ } from "@contentflow/ui/components";
import { CTAFooter } from "@contentflow/ui/components";
import { Footer } from "@contentflow/ui/components";

const SECTION_MAP: Record<string, React.ReactNode> = {
  hero: (
    <Hero
      key="hero"
      headline={config.landing.hero.headline}
      sub={config.landing.hero.sub}
      cta={config.landing.hero.cta_primary}
      ctaSecondary={config.landing.hero.cta_secondary}
    />
  ),
  how_it_works: <HowItWorks key="how_it_works" />,
  platforms: (
    <PlatformGrid
      key="platforms"
      platforms={config.features.platforms_hero}
      title="Distribute everywhere"
    />
  ),
  pricing: (
    <PricingTable
      key="pricing"
      plans={config.pricing.plans}
      currency={config.pricing.currency}
    />
  ),
  faq: <FAQ key="faq" />,
  cta_footer: (
    <CTAFooter key="cta_footer" cta={config.landing.hero.cta_primary} />
  ),
};

export default function LandingPage() {
  return (
    <main>
      {config.landing.sections.map((section) => SECTION_MAP[section] ?? null)}
      <Footer name={config.name} domain={config.domain.primary} />
    </main>
  );
}
