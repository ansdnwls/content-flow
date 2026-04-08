import React, { useState } from "react";

interface FAQItem {
  readonly question: string;
  readonly answer: string;
}

interface FAQProps {
  readonly items?: readonly FAQItem[];
  readonly title?: string;
}

const DEFAULT_FAQ: FAQItem[] = [
  {
    question: "How does the free plan work?",
    answer:
      "The free plan gives you access to core features with limited usage. No credit card required.",
  },
  {
    question: "Can I switch plans later?",
    answer:
      "Yes, you can upgrade or downgrade at any time. Changes take effect immediately.",
  },
  {
    question: "What platforms are supported?",
    answer:
      "We support all major social media platforms including YouTube, TikTok, Instagram, X, Facebook, LinkedIn, and more.",
  },
  {
    question: "Is there an API?",
    answer:
      "Yes, we provide a full REST API and SDKs for Go, Python, and TypeScript.",
  },
];

export function FAQ({ items = DEFAULT_FAQ, title = "FAQ" }: FAQProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section className="py-20 px-6" id="faq">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-12 text-[var(--color-text)]">
          {title}
        </h2>
        <div className="space-y-4">
          {items.map((item, i) => (
            <div
              key={i}
              className="border border-[var(--color-text)]/10 rounded-xl overflow-hidden"
            >
              <button
                onClick={() => setOpenIndex(openIndex === i ? null : i)}
                className="w-full px-6 py-4 text-left flex items-center justify-between text-[var(--color-text)] hover:bg-[var(--color-text)]/5 transition-colors"
              >
                <span className="font-medium">{item.question}</span>
                <span className="text-xl">{openIndex === i ? "\u2212" : "+"}</span>
              </button>
              {openIndex === i && (
                <div className="px-6 pb-4 text-[var(--color-text)]/70">
                  {item.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
