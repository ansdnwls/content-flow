import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Link } from "@/i18n/navigation";
import { useCases } from "@/lib/marketing";

type Props = {
  params: Promise<{ slug: string; locale: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const useCase = useCases.find((entry) => entry.slug === slug);

  if (!useCase) {
    return {};
  }

  return {
    title: `ContentFlow for ${useCase.shortTitle}`,
    description: useCase.description,
    openGraph: {
      images: [
        {
          url: `/api/og?title=${encodeURIComponent(useCase.kicker)}&subtitle=${encodeURIComponent(useCase.shortTitle)}&platform=${encodeURIComponent(slug === "korean-businesses" ? "naver-blog" : "youtube")}`,
          width: 1200,
          height: 630,
        },
      ],
    },
  };
}

export default async function UseCasePage({ params }: Props) {
  const { slug } = await params;
  const useCase = useCases.find((entry) => entry.slug === slug);

  if (!useCase) {
    notFound();
  }

  return (
    <div className="page docs-page">
      <section className="section docs-hero">
        <span className="eyebrow">{useCase.persona}</span>
        <h1>{useCase.title}</h1>
        <p className="docs-hero__lede">{useCase.description}</p>
      </section>

      <section className="section">
        <div className="docs-grid">
          <article className="docs-card">
            <h3>Problem</h3>
            <p>{useCase.kicker}</p>
            <ul>
              <li>Too many channels, not enough operators</li>
              <li>Regional endpoints break the default tool stack</li>
              <li>Manual replies kill publishing momentum</li>
            </ul>
          </article>

          <article className="docs-card">
            <h3>Solution</h3>
            <p>Use ContentFlow as the orchestration layer so your publish burst, reply handling, and platform routing all run together.</p>
            <ul>
              <li>Best-fit plan: {useCase.highlightPlan}</li>
              <li>Channel-native copy and publish routing</li>
              <li>Comment Autopilot as the follow-through layer</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="section">
        <div className="docs-card docs-card--wide">
          <h3>Example call</h3>
          <pre className="code-shell__body" style={{ paddingLeft: 0, paddingRight: 0 }}>
            <code>{useCase.codeExample}</code>
          </pre>
          <div className="spotlight__actions">
            <a className="button button--primary button--xl" href="/#pricing">
              {useCase.cta}
            </a>
            <Link className="button button--ghost button--xl" href="/docs">
              API docs
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
