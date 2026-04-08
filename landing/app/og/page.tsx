export default function OgGalleryPage() {
  const previews = [
    { title: "One topic. 21 platforms. Zero clicks.", subtitle: "Main page OG", platform: "youtube" },
    { title: "From $0 to Enterprise", subtitle: "Pricing page OG", platform: "kakao" },
    { title: "1 API. 21 Platforms.", subtitle: "Features page OG", platform: "line" },
  ];

  return (
    <div className="page docs-page">
      <section className="section docs-hero">
        <span className="eyebrow">OG preview</span>
        <h1>Marketing link previews that do the first five seconds for you.</h1>
        <p className="docs-hero__lede">These images are generated from the shared OG API so page, blog, and campaign links keep the same visual language.</p>
      </section>

      <section className="section">
        <div className="docs-grid">
          {previews.map((preview) => (
            <article className="docs-card" key={preview.subtitle}>
              <h3>{preview.subtitle}</h3>
              <img
                src={`/api/og?title=${encodeURIComponent(preview.title)}&subtitle=${encodeURIComponent(preview.subtitle)}&platform=${preview.platform}`}
                alt={preview.title}
                style={{ width: "100%", borderRadius: "24px", border: "1px solid rgba(255,173,129,0.24)" }}
              />
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
