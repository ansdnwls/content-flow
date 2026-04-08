import React from "react";

interface Step {
  readonly title: string;
  readonly description: string;
}

interface HowItWorksProps {
  readonly steps?: readonly Step[];
  readonly title?: string;
}

const DEFAULT_STEPS: Step[] = [
  { title: "Connect", description: "Link your social media accounts in one click." },
  { title: "Create", description: "Write once, distribute everywhere automatically." },
  { title: "Grow", description: "Track analytics and optimize your reach." },
];

export function HowItWorks({
  steps = DEFAULT_STEPS,
  title = "How it works",
}: HowItWorksProps) {
  return (
    <section className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16 text-[var(--color-text)]">
          {title}
        </h2>
        <div className="grid md:grid-cols-3 gap-12">
          {steps.map((step, i) => (
            <div key={i} className="text-center">
              <div className="w-12 h-12 rounded-full bg-[var(--color-primary)] text-white flex items-center justify-center text-xl font-bold mx-auto mb-4">
                {i + 1}
              </div>
              <h3 className="text-xl font-semibold mb-2 text-[var(--color-text)]">
                {step.title}
              </h3>
              <p className="text-[var(--color-text)]/70">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
