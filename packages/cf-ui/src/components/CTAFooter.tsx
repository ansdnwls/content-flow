import React from "react";

interface CTAFooterProps {
  readonly headline?: string;
  readonly sub?: string;
  readonly cta: string;
  readonly onCtaClick?: () => void;
}

export function CTAFooter({
  headline = "Ready to get started?",
  sub = "Start for free, no credit card required.",
  cta,
  onCtaClick,
}: CTAFooterProps) {
  return (
    <section className="py-24 px-6">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-4xl font-bold mb-4 text-[var(--color-text)]">
          {headline}
        </h2>
        <p className="text-xl text-[var(--color-text)]/70 mb-8">{sub}</p>
        <button
          onClick={onCtaClick}
          className="px-8 py-4 bg-[var(--color-primary)] text-white rounded-xl text-lg font-semibold hover:opacity-90 transition-opacity"
        >
          {cta}
        </button>
      </div>
    </section>
  );
}
