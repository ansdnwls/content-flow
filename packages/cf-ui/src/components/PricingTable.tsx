import React from "react";
import type { PlanConfig } from "@contentflow/config";
import { formatPrice } from "@contentflow/config";

interface PricingTableProps {
  readonly plans: readonly PlanConfig[];
  readonly currency: string;
  readonly onSelect?: (planId: string) => void;
}

export function PricingTable({ plans, currency, onSelect }: PricingTableProps) {
  return (
    <section className="py-20 px-6" id="pricing">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-12 text-[var(--color-text)]">
          Simple pricing
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          {plans.map((plan, i) => {
            const isPopular = i === 1;
            return (
              <div
                key={plan.id}
                className={`rounded-2xl p-8 ${
                  isPopular
                    ? "bg-[var(--color-primary)] text-white ring-2 ring-[var(--color-primary)] scale-105"
                    : "bg-[var(--color-text)]/5 text-[var(--color-text)]"
                }`}
              >
                <h3 className="text-xl font-semibold mb-2">{plan.name}</h3>
                <div className="text-4xl font-bold mb-6">
                  {plan.price_monthly === 0
                    ? "Free"
                    : `${formatPrice(plan.price_monthly, currency)}/mo`}
                </div>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <span className="mt-1 shrink-0">&#10003;</span>
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => onSelect?.(plan.id)}
                  className={`w-full py-3 rounded-xl font-semibold transition-opacity hover:opacity-90 ${
                    isPopular
                      ? "bg-white text-[var(--color-primary)]"
                      : "bg-[var(--color-primary)] text-white"
                  }`}
                >
                  {plan.price_monthly === 0 ? "Start free" : "Get started"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
