"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CONSENT_STORAGE_KEY = "contentflow-cookie-consent";
const CONSENT_TTL_MS = 365 * 24 * 60 * 60 * 1000;

type ConsentPreferences = {
  essential: true;
  functional: boolean;
  analytics: boolean;
  savedAt: string;
  expiresAt: string;
};

type ConsentDraft = {
  functional: boolean;
  analytics: boolean;
};

function buildStoredPreferences(draft: ConsentDraft): ConsentPreferences {
  const now = new Date();
  return {
    essential: true,
    functional: draft.functional,
    analytics: draft.analytics,
    savedAt: now.toISOString(),
    expiresAt: new Date(now.getTime() + CONSENT_TTL_MS).toISOString(),
  };
}

function readStoredConsent(): ConsentPreferences | null {
  try {
    const raw = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<ConsentPreferences>;
    if (!parsed.expiresAt || Date.parse(parsed.expiresAt) <= Date.now()) {
      return null;
    }
    return {
      essential: true,
      functional: Boolean(parsed.functional),
      analytics: Boolean(parsed.analytics),
      savedAt: parsed.savedAt ?? new Date().toISOString(),
      expiresAt: parsed.expiresAt,
    };
  } catch {
    return null;
  }
}

async function syncConsentPreferences(draft: ConsentDraft) {
  const apiKey = window.localStorage.getItem("cf_api_key") ?? "";
  const grantPurposes = [
    "essential",
    ...(draft.functional ? ["cookies_functional"] : []),
    ...(draft.analytics ? ["analytics", "cookies_analytics"] : []),
  ];
  const revokePurposes = [
    ...(draft.functional ? [] : ["cookies_functional"]),
    ...(draft.analytics ? [] : ["analytics", "cookies_analytics"]),
  ];

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  await fetch(`${API_URL}/api/v1/consent/grant`, {
    method: "POST",
    headers,
    body: JSON.stringify({ purposes: grantPurposes }),
  }).catch(() => undefined);

  if (revokePurposes.length > 0) {
    await fetch(`${API_URL}/api/v1/consent/revoke`, {
      method: "POST",
      headers,
      body: JSON.stringify({ purposes: revokePurposes }),
    }).catch(() => undefined);
  }
}

export function CookieBanner() {
  const [ready, setReady] = useState(false);
  const [open, setOpen] = useState(false);
  const [customize, setCustomize] = useState(false);
  const [draft, setDraft] = useState<ConsentDraft>({
    functional: false,
    analytics: false,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const stored = readStoredConsent();
    if (stored) {
      setDraft({
        functional: stored.functional,
        analytics: stored.analytics,
      });
    } else {
      setOpen(true);
    }
    setReady(true);
  }, []);

  async function persistConsent(nextDraft: ConsentDraft) {
    setSaving(true);
    const stored = buildStoredPreferences(nextDraft);
    window.localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify(stored));
    setDraft(nextDraft);
    await syncConsentPreferences(nextDraft);
    setSaving(false);
    setCustomize(false);
    setOpen(false);
  }

  if (!ready || !open) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[70] px-4 pb-4 sm:px-6 lg:px-8">
      <section className="pointer-events-auto mx-auto max-w-5xl overflow-hidden rounded-[28px] border border-border-strong/70 bg-bg/95 shadow-[0_28px_90px_rgba(7,4,9,0.55)] backdrop-blur-2xl">
        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[1.2fr,0.8fr] lg:items-start">
          <div>
            <span className="pill">Cookie preferences</span>
            <h2 className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-text">
              Control how ContentFlow remembers and measures your workspace.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
              Essential cookies stay on so sign-in and security controls work. Functional cookies
              keep dashboard preferences stable, and analytics cookies help us understand product
              usage. We ask again after one year.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-primary flex-1"
                disabled={saving}
                onClick={() => persistConsent({ functional: true, analytics: true })}
              >
                Accept all
              </button>
              <button
                type="button"
                className="btn-secondary flex-1"
                disabled={saving}
                onClick={() => persistConsent({ functional: false, analytics: false })}
              >
                Reject all
              </button>
            </div>
            <button
              type="button"
              className="btn-ghost w-full"
              onClick={() => setCustomize((value) => !value)}
            >
              {customize ? "Hide customization" : "Customize"}
            </button>
          </div>
        </div>

        <div
          className={cn(
            "grid gap-3 border-t border-border/50 bg-card-hover/35 px-5 py-4 transition-all sm:px-6",
            customize ? "max-h-[420px] opacity-100" : "max-h-0 overflow-hidden border-t-0 py-0 opacity-0"
          )}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <article className="glass-card--soft rounded-[24px] border p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-text">Essential</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    Authentication, session continuity, security, and fraud prevention.
                  </p>
                </div>
                <span className="toggle-chip is-active">Required</span>
              </div>
            </article>

            <article className="glass-card--soft rounded-[24px] border p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-text">Functional</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    Theme, language, and dashboard convenience settings across visits.
                  </p>
                </div>
                <button
                  type="button"
                  className={cn("toggle-chip", draft.functional && "is-active")}
                  onClick={() => setDraft((current) => ({ ...current, functional: !current.functional }))}
                >
                  {draft.functional ? "On" : "Off"}
                </button>
              </div>
            </article>

            <article className="glass-card--soft rounded-[24px] border p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-text">Analytics</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    Product usage analytics and performance signals for feature improvement.
                  </p>
                </div>
                <button
                  type="button"
                  className={cn("toggle-chip", draft.analytics && "is-active")}
                  onClick={() => setDraft((current) => ({ ...current, analytics: !current.analytics }))}
                >
                  {draft.analytics ? "On" : "Off"}
                </button>
              </div>
            </article>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <p className="text-xs leading-5 text-muted">
              Your choice is stored in local storage and revisited after 365 days.
            </p>
            <button
              type="button"
              className="btn-primary"
              disabled={saving}
              onClick={() => persistConsent(draft)}
            >
              Save preferences
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
