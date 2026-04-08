import { platforms } from "@/lib/site-data";

export function PlatformGrid() {
  return (
    <div className="platform-grid">
      {platforms.map((platform) => (
        <article className="platform-chip" key={platform.name}>
          <div className="platform-chip__topline">
            <span className="platform-chip__mark" style={{ color: platform.color }}>
              {platform.glyph}
            </span>
            {"badge" in platform ? <span className="platform-chip__badge">{platform.badge}</span> : null}
          </div>
          <div className="platform-chip__copy">
            <span className="platform-chip__name">{platform.name}</span>
            <span className="platform-chip__meta">{platform.category}</span>
          </div>
        </article>
      ))}
    </div>
  );
}
