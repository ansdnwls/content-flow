import type { Metadata } from "next";

import { featureCards } from "@/lib/site-data";

export const metadata: Metadata = {
  title: "ContentFlow Features",
  description: "1 API. 21 Platforms. Built for generation, distribution, and reply operations.",
  openGraph: {
    images: [
      {
        url: "/api/og?title=1%20API.%2021%20Platforms.&subtitle=Built%20for%20generation%2C%20distribution%2C%20and%20reply%20operations&platform=line",
        width: 1200,
        height: 630,
      },
    ],
  },
};

export default function FeaturesPage() {
  return (
    <div className="page docs-page">
      <section className="section docs-hero">
        <span className="eyebrow">Features</span>
        <h1>Generation, distribution, and replies in one rail.</h1>
        <p className="docs-hero__lede">The core system is three layers deep: burst creation, reply operations, and signal scoring before money or time gets burned.</p>
      </section>

      <section className="section">
        <div className="feature-grid">
          {featureCards.map((feature, index) => (
            <article className="feature-card" key={feature.title}>
              <span className="feature-card__eyebrow">{feature.eyebrow}</span>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
              <div className="feature-card__mini-demo">
                <span className="feature-card__mini-demo-bar" style={{ width: `${74 + index * 8}%` }} />
              </div>
              <div className="feature-card__bullet">{feature.bullet}</div>
              <div className="feature-card__stat">{feature.stat}</div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
