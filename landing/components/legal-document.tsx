import { LegalDocument as LegalDocumentType, LEGAL_LAST_UPDATED } from "@/lib/legal-content";

export function LegalDocument({ document }: { document: LegalDocumentType }) {
  return (
    <article className="legal-document">
      <header className="legal-document__header">
        <span className="eyebrow">Legal text</span>
        <h1>{document.title}</h1>
        <p className="legal-document__summary">{document.summary}</p>
        <div className="legal-meta">
          <span>Last updated</span>
          <strong>{LEGAL_LAST_UPDATED}</strong>
        </div>
      </header>

      <div className="legal-intro">
        {document.intro.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
      </div>

      <div className="legal-section-list">
        {document.sections.map((section) => (
          <section className="legal-section" key={section.title}>
            <h2>{section.title}</h2>
            {section.body.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            {section.bullets ? (
              <ul>
                {section.bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
      </div>

      <footer className="legal-footnote">
        <strong>Footnote.</strong> {document.footnote}
      </footer>
    </article>
  );
}
