import React from "react";

interface HeroProps {
  readonly headline: string;
  readonly sub: string;
  readonly cta: string;
  readonly ctaSecondary?: string;
  readonly onCtaClick?: () => void;
  readonly onSecondaryClick?: () => void;
}

export function Hero({
  headline,
  sub,
  cta,
  ctaSecondary,
  onCtaClick,
  onSecondaryClick,
}: HeroProps) {
  return (
    <section className="relative min-h-[80vh] flex items-center justify-center px-6 py-24">
      <div className="max-w-4xl mx-auto text-center">
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 text-[var(--color-text)]">
          {headline}
        </h1>
        <p className="text-xl md:text-2xl text-[var(--color-text)]/70 mb-10 max-w-2xl mx-auto">
          {sub}
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button
            onClick={onCtaClick}
            className="px-8 py-4 bg-[var(--color-primary)] text-white rounded-xl text-lg font-semibold hover:opacity-90 transition-opacity"
          >
            {cta}
          </button>
          {ctaSecondary && (
            <button
              onClick={onSecondaryClick}
              className="px-8 py-4 border border-[var(--color-text)]/20 text-[var(--color-text)] rounded-xl text-lg font-semibold hover:bg-[var(--color-text)]/5 transition-colors"
            >
              {ctaSecondary}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
