import type { Metadata } from "next";

import { Link } from "@/i18n/navigation";
import { pricingPlans } from "@/lib/site-data";

export const metadata: Metadata = {
  title: "ContentFlow Pricing",
  description: "From $0 to Enterprise. Buy leverage, not more dashboard debt.",
  openGraph: {
    images: [
      {
        url: "/api/og?title=From%20%240%20to%20Enterprise&subtitle=Buy%20leverage%2C%20not%20more%20dashboard%20debt&platform=kakao",
        width: 1200,
        height: 630,
      },
    ],
  },
};

export default function PricingPage() {
  return (
    <div className="page docs-page">
      <section className="section docs-hero">
        <span className="eyebrow">Pricing</span>
        <h1>From $0 to Enterprise.</h1>
        <p className="docs-hero__lede">The pricing model is simple: start free, prove the burst, and scale once the workflow carries real volume.</p>
      </section>

      <section className="section">
        <div className="pricing-grid">
          {pricingPlans.map((plan) => (
            <article className={`price-card${plan.highlight ? " price-card--featured" : ""}`} key={plan.name}>
              <div className="price-card__header">
                <div>
                  <h3>{plan.name}</h3>
                  <p>{plan.description}</p>
                </div>
                {plan.highlight ? <span className="price-card__badge">Most Popular</span> : null}
              </div>
              <div className="price-card__price">
                <span>{plan.monthly === null ? "Custom" : `$${plan.monthly}`}</span>
                <small>{plan.monthly === null ? "contact us" : plan.cadence}</small>
              </div>
              <ul className="price-card__features">
                {plan.features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <div className="section--spotlight" style={{ paddingTop: 32 }}>
          <div className="spotlight">
            <div className="spotlight__copy">
              <span className="eyebrow">Need more?</span>
              <h2>Need private onboarding or compliance review?</h2>
              <p>Enterprise covers white-label, governance, and roadmap collaboration for teams that need more than self-serve setup.</p>
            </div>
            <Link className="button button--primary button--xl" href="/docs">
              Talk to the API
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
