"use client";

import { CSSProperties, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { CodeBlock } from "@/components/code-block";
import { InteractiveDemo } from "@/components/interactive-demo";
import { PlatformGrid } from "@/components/platform-grid";
import {
  goSnippet,
  javascriptSnippet,
  platforms,
  pricingPlans,
  proofLogos,
  pythonSnippet,
  socialProofStats,
} from "@/lib/site-data";

type ThemeCodeTab = "python" | "javascript" | "go";

const CODE_TABS: { id: ThemeCodeTab; label: string; language: string; code: typeof pythonSnippet }[] = [
  { id: "python", label: "Python SDK", language: "python", code: pythonSnippet },
  { id: "javascript", label: "JavaScript SDK", language: "javascript", code: javascriptSnippet },
  { id: "go", label: "Go SDK", language: "go", code: goSnippet },
];

const FEATURE_KEYS = ["bomb", "autopilot", "viral"] as const;
const PLAN_KEYS = ["free", "build", "scale", "enterprise"] as const;

function CountUp({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    let frame = 0;
    const duration = 1200;
    const start = performance.now();

    function tick(now: number) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - (1 - progress) * (1 - progress);
      setCurrent(Math.round(value * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    }

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return (
    <span>
      {current.toLocaleString()}
      {suffix}
    </span>
  );
}

export default function HomePage() {
  const tHero = useTranslations("hero");
  const tBurst = useTranslations("burst_field");
  const tCode = useTranslations("code_demo");
  const tPlatforms = useTranslations("platforms");
  const tFeatures = useTranslations("features");
  const tPricing = useTranslations("pricing");
  const tProof = useTranslations("proof");
  const tFaq = useTranslations("faq");
  const tCta = useTranslations("cta");
  const tRail = useTranslations("rail");
  const tTestimonials = useTranslations("testimonials");

  const [annual, setAnnual] = useState(true);
  const [activeCode, setActiveCode] = useState<ThemeCodeTab>("python");
  const [activeQuote, setActiveQuote] = useState(0);
  const [cursor, setCursor] = useState({ x: 50, y: 45 });

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveCode((prev) => {
        const index = CODE_TABS.findIndex((tab) => tab.id === prev);
        return CODE_TABS[(index + 1) % CODE_TABS.length].id;
      });
    }, 2800);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveQuote((prev) => (prev + 1) % 3);
    }, 4200);

    return () => window.clearInterval(timer);
  }, []);

  const currentCode = CODE_TABS.find((tab) => tab.id === activeCode) ?? CODE_TABS[0];

  const statKeys = ["teams", "actions", "minutes"] as const;

  const statusLabel = (index: number) => {
    if (index % 3 === 0) return tCode("queued");
    if (index % 3 === 1) return tCode("posted");
    return tCode("localized");
  };

  const statusClass = (index: number) => {
    if (index % 3 === 0) return "queued";
    if (index % 3 === 1) return "posted";
    return "localized";
  };

  return (
    <div className="page">
      <section
        className="hero section"
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          setCursor({
            x: ((event.clientX - rect.left) / rect.width) * 100,
            y: ((event.clientY - rect.top) / rect.height) * 100,
          });
        }}
      >
        <div
          className="hero__spotlight"
          aria-hidden="true"
          style={
            {
              "--spot-x": `${cursor.x}%`,
              "--spot-y": `${cursor.y}%`,
            } as CSSProperties
          }
        />
        <div className="hero__copy">
          <span className="eyebrow">{tHero("eyebrow")}</span>
          <p className="hero__kicker">{tHero("kicker")}</p>
          <h1>{tHero("headline")}</h1>
          <p className="hero__lede">{tHero("lede")}</p>
          <div className="hero__actions">
            <a className="button button--primary button--xl" href="#pricing">
              {tHero("cta_primary")}
            </a>
            <Link className="button button--ghost button--xl" href="/docs">
              {tHero("cta_secondary")}
            </Link>
          </div>
          <div className="hero__proof">
            <span>{tHero("proof_1")}</span>
            <span>{tHero("proof_2")}</span>
            <span>{tHero("proof_3")}</span>
          </div>
        </div>
        <div className="hero__visual">
          <div className="burst-field">
            <div className="burst-field__center">
              <span className="burst-field__core" />
              <strong>{tBurst("center_title")}</strong>
              <small>{tBurst("center_subtitle")}</small>
            </div>
            {platforms.map((platform, index) => (
              <div
                key={platform.name}
                className="burst-node"
                style={
                  {
                    "--angle": `${(360 / platforms.length) * index}deg`,
                    "--distance": `${168 + (index % 4) * 12}px`,
                    "--delay": `${index * 90}ms`,
                    "--node-color": platform.color,
                  } as CSSProperties
                }
              >
                <span className="burst-node__glyph">{platform.glyph}</span>
                <span className="burst-node__label">{platform.name}</span>
              </div>
            ))}
          </div>
          <div className="hero__rail">
            <div className="hero__rail-card">
              <span className="hero__rail-label">{tRail("label")}</span>
              <ul className="hero__rail-list">
                {[0, 1, 2, 3].map((i) => (
                  <li key={i}>{tRail(`items.${i}`)}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--code">
        <div className="section-heading">
          <span className="eyebrow">{tCode("eyebrow")}</span>
          <h2>{tCode("title")}</h2>
          <p>{tCode("description")}</p>
        </div>
        <div className="code-demo">
          <div className="code-demo__main">
            <div className="code-tabs" role="tablist" aria-label="SDK language">
              {CODE_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeCode === tab.id}
                  className={`code-tabs__tab${activeCode === tab.id ? " is-active" : ""}`}
                  onClick={() => setActiveCode(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <CodeBlock code={currentCode.code} label={currentCode.label} language={currentCode.language} />
          </div>
          <div className="code-demo__feed">
            <div className="live-feed">
              <div className="live-feed__header">
                <span className="eyebrow eyebrow--compact">{tCode("live_distribution")}</span>
                <strong>{tCode("fan_out")}</strong>
              </div>
              <div className="live-feed__list">
                {platforms.slice(0, 8).map((platform, index) => (
                  <div className="live-feed__item" key={platform.name}>
                    <span className="live-feed__platform">{platform.name}</span>
                    <span className={`live-feed__status live-feed__status--${statusClass(index)}`}>
                      {statusLabel(index)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <InteractiveDemo />

      <section className="section" id="platforms">
        <div className="section-heading">
          <span className="eyebrow">{tPlatforms("eyebrow")}</span>
          <h2>{tPlatforms("title")}</h2>
          <p>{tPlatforms("description")}</p>
        </div>
        <PlatformGrid />
      </section>

      <section className="section" id="features">
        <div className="section-heading">
          <span className="eyebrow">{tFeatures("eyebrow")}</span>
          <h2>{tFeatures("title")}</h2>
        </div>
        <div className="feature-grid">
          {FEATURE_KEYS.map((key, index) => (
            <article className="feature-card" key={key}>
              <span className="feature-card__eyebrow">{tFeatures(`cards.${key}.eyebrow`)}</span>
              <h3>{tFeatures(`cards.${key}.title`)}</h3>
              <p>{tFeatures(`cards.${key}.description`)}</p>
              <div className="feature-card__mini-demo">
                <span className="feature-card__mini-demo-bar" style={{ width: `${72 + index * 8}%` }} />
              </div>
              <div className="feature-card__bullet">{tFeatures(`cards.${key}.bullet`)}</div>
              <div className="feature-card__stat">{tFeatures(`cards.${key}.stat`)}</div>
            </article>
          ))}
        </div>
      </section>

      <section className="section" id="pricing">
        <div className="section-heading">
          <span className="eyebrow">{tPricing("eyebrow")}</span>
          <h2>{tPricing("title")}</h2>
        </div>
        <div className="billing-toggle" role="group" aria-label="Billing cadence">
          <button
            type="button"
            className={`billing-toggle__option${!annual ? " is-active" : ""}`}
            onClick={() => setAnnual(false)}
          >
            {tPricing("monthly")}
          </button>
          <button
            type="button"
            className={`billing-toggle__option${annual ? " is-active" : ""}`}
            onClick={() => setAnnual(true)}
          >
            {tPricing("annual")}
          </button>
        </div>
        <div className="pricing-grid">
          {PLAN_KEYS.map((key) => {
            const planData = pricingPlans.find(
              (p) => p.name.toLowerCase() === key
            ) ?? pricingPlans[0];
            const price = annual ? planData.yearly : planData.monthly;
            const isHighlight = planData.highlight;

            const features = tPricing.raw(`plans.${key}.features`) as string[];

            return (
              <article className={`price-card${isHighlight ? " price-card--featured" : ""}`} key={key}>
                <div className="price-card__header">
                  <div>
                    <h3>{tPricing(`plans.${key}.name`)}</h3>
                    <p>{tPricing(`plans.${key}.description`)}</p>
                  </div>
                  {isHighlight ? <span className="price-card__badge">{tPricing("most_popular")}</span> : null}
                </div>
                <div className="price-card__price">
                  <span>{price === null ? tPricing("custom") : `$${price}`}</span>
                  <small>{price === null ? tPricing("talk_to_us") : tPricing("month")}</small>
                </div>
                <ul className="price-card__features">
                  {features.map((feature: string) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <span className="eyebrow">{tProof("eyebrow")}</span>
          <h2>{tProof("title")}</h2>
        </div>
        <div className="proof-grid">
          {socialProofStats.map((stat, index) => (
            <article className="proof-card" key={statKeys[index]}>
              <strong>
                <CountUp value={stat.value} suffix={stat.value > 999 ? "+" : ""} />
              </strong>
              <span>{tProof(`stats.${statKeys[index]}`)}</span>
            </article>
          ))}
        </div>
        <div className="logo-marquee" aria-label="Example customer logos">
          {proofLogos.map((logo) => (
            <span key={logo}>{logo}</span>
          ))}
        </div>
        <div className="testimonial-grid testimonial-grid--featured">
          {[0, 1, 2].map((index) => (
            <article
              className={`testimonial-card${activeQuote === index ? " is-active" : ""}`}
              key={index}
            >
              <p>&ldquo;{tTestimonials(`${index}.quote`)}&rdquo;</p>
              <div>
                <strong>{tTestimonials(`${index}.name`)}</strong>
                <span>{tTestimonials(`${index}.role`)}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <span className="eyebrow">{tFaq("eyebrow")}</span>
          <h2>{tFaq("title")}</h2>
        </div>
        <div className="faq-list">
          {[0, 1, 2, 3].map((i) => (
            <details className="faq-item" key={i}>
              <summary>{tFaq(`items.${i}.question`)}</summary>
              <p>{tFaq(`items.${i}.answer`)}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="section section--spotlight">
        <div className="spotlight">
          <div className="spotlight__copy">
            <span className="eyebrow">{tCta("eyebrow")}</span>
            <h2>{tCta("title")}</h2>
            <p>{tCta("description")}</p>
          </div>
          <div className="spotlight__actions">
            <a className="button button--primary button--xl" href="#pricing">
              {tCta("cta_primary")}
            </a>
            <Link className="button button--ghost button--xl" href="/docs">
              {tCta("cta_secondary")}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
