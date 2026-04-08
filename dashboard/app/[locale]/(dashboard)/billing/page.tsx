"use client";

import { useTranslations } from "next-intl";
import { CreditCard, ExternalLink, FileText } from "lucide-react";

const PLANS = [
  { name: "Free", key: "free", price: "$0", current: true },
  { name: "Build", key: "build", price: "$29", current: false },
  { name: "Scale", key: "scale", price: "$99", current: false },
];

const INVOICES = [
  { date: "2026-04-01", amount: "$0.00", status: "paid" },
  { date: "2026-03-01", amount: "$0.00", status: "paid" },
];

export default function BillingPage() {
  const t = useTranslations("billing");

  async function handleCheckout(plan: string) {
    const API_URL =
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const apiKey = localStorage.getItem("cf_api_key") ?? "";
    const res = await fetch(`${API_URL}/api/v1/billing/checkout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ plan }),
    });
    const data = await res.json();
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {/* Current plan */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm text-muted">{t("current_plan")}</span>
            <div className="text-xl font-bold text-accent">{t("free")}</div>
          </div>
          <div className="text-right text-sm text-muted">
            <div>42 / 100 {t("posts_used")}</div>
            <div>{t("next_billing")}: —</div>
          </div>
        </div>
        <div className="h-2 bg-card rounded-full overflow-hidden mt-3">
          <div
            className="h-full bg-gradient-accent rounded-full"
            style={{ width: "42%" }}
          />
        </div>
      </div>

      {/* Plans */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PLANS.map((plan) => (
          <div
            key={plan.name}
            className={`glass-card p-5 space-y-4 ${
              plan.current ? "border-accent/40 border" : ""
            }`}
          >
            <div>
              <h3 className="text-lg font-bold">{plan.name}</h3>
              <div className="text-2xl font-bold mt-1">
                {plan.price}
                <span className="text-sm text-muted font-normal">/{t("month")}</span>
              </div>
            </div>
            <ul className="space-y-2">
              {(t.raw(`plans.${plan.key}.features`) as string[]).map((f) => (
                <li key={f} className="text-sm text-muted flex items-center gap-2">
                  <span className="text-success">✓</span> {f}
                </li>
              ))}
            </ul>
            {plan.current ? (
              <button className="btn-secondary w-full" disabled>
                {t("current_plan")}
              </button>
            ) : (
              <button
                className="btn-primary w-full"
                onClick={() => handleCheckout(plan.name.toLowerCase())}
              >
                {t("upgrade_to", { plan: plan.name })}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Payment management */}
      <div className="glass-card p-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CreditCard size={20} className="text-muted" />
          <span className="text-sm">{t("manage_payment")}</span>
        </div>
        <button className="btn-secondary flex items-center gap-2 text-sm">
          <ExternalLink size={14} /> {t("stripe_portal")}
        </button>
      </div>

      {/* Invoices */}
      <div className="glass-card">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="font-semibold">{t("invoices")}</h3>
        </div>
        <div className="divide-y divide-border">
          {INVOICES.map((inv, i) => (
            <div
              key={i}
              className="px-5 py-3 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-muted" />
                <span className="text-sm">{inv.date}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted">{inv.amount}</span>
                <span className="text-xs text-success">{inv.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
