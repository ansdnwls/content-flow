import type { Metadata } from "next";

import { Link } from "@/i18n/navigation";
import { useCases } from "@/lib/marketing";

export const metadata: Metadata = {
  title: "ContentFlow Use Cases",
  description: "Persona-led landing pages for creators, agencies, SaaS builders, and Korean businesses.",
  openGraph: {
    images: [
      {
        url: "/api/og?title=Use%20Cases%20for%20Creators%2C%20Agencies%2C%20and%20Builders&subtitle=Find%20the%20burst%20that%20fits%20your%20workflow&platform=linkedin",
        width: 1200,
        height: 630,
      },
    ],
  },
};

export default function UseCasesIndexPage() {
  return (
    <div className="page docs-page">
      <section className="section docs-hero">
        <span className="eyebrow">Use cases</span>
        <h1>The same engine, tuned for different operators.</h1>
        <p className="docs-hero__lede">ContentFlow can look like a creator shortcut, an agency throughput system, or an integration layer depending on who is using it.</p>
      </section>

      <section className="section">
        <div className="docs-grid">
          {useCases.map((useCase) => (
            <article className="docs-card" key={useCase.slug}>
              <span className="feature-card__eyebrow">{useCase.persona}</span>
              <h3>{useCase.shortTitle}</h3>
              <p>{useCase.description}</p>
              <Link className="button button--ghost" href={`/use-cases/${useCase.slug}`}>
                Open page
              </Link>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
