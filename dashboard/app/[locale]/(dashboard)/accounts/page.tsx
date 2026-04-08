"use client";

import { useTranslations } from "next-intl";
import { EmptyState } from "@/components/empty-state";
import { PlatformIcon } from "@/components/platform-icon";
import { Plus, Unlink, AlertTriangle } from "lucide-react";

const PLATFORMS = [
  "youtube",
  "tiktok",
  "instagram",
  "x_twitter",
  "linkedin",
  "medium",
  "mastodon",
  "line",
];

const CONNECTED = [
  {
    platform: "youtube",
    username: "@contentflow",
    connected_at: "2026-03-15",
    token_expires: "2026-05-15",
    healthy: true,
  },
  {
    platform: "x_twitter",
    username: "@cf_official",
    connected_at: "2026-03-20",
    token_expires: "2026-04-08",
    healthy: false,
  },
  {
    platform: "linkedin",
    username: "ContentFlow Inc.",
    connected_at: "2026-04-01",
    token_expires: "2026-06-01",
    healthy: true,
  },
];

export default function AccountsPage() {
  const t = useTranslations("accounts");
  const connectedPlatforms = CONNECTED.map((c) => c.platform);
  const available = PLATFORMS.filter((p) => !connectedPlatforms.includes(p));

  if (CONNECTED.length === 0) {
    return (
      <EmptyState
        title="Connect your first account"
        description="Once an account is connected, ContentFlow can start routing real publish jobs into the network."
        image="/illustrations/empty-accounts.svg"
        actionLabel="Connect account"
        actionHref="/en/accounts"
      />
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {/* Connected */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {CONNECTED.map((acct) => (
          <div key={acct.platform} className="glass-card p-5 space-y-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <PlatformIcon platform={acct.platform} size={24} />
                <div>
                  <div className="font-semibold capitalize">
                    {acct.platform.replace("_", " ")}
                  </div>
                  <div className="text-sm text-muted">{acct.username}</div>
                </div>
              </div>
              {!acct.healthy && (
                <AlertTriangle size={18} className="text-danger" />
              )}
            </div>
            {!acct.healthy && (
              <div className="text-xs text-danger bg-danger/10 rounded-lg p-2">
                {t("token_expiring")}
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted">
                Connected {acct.connected_at}
              </span>
              <button className="text-xs text-danger hover:underline flex items-center gap-1">
                <Unlink size={12} /> {t("disconnect")}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Available */}
      {available.length > 0 && (
        <>
          <h2 className="text-lg font-semibold mt-8">{t("connect_new")}</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {available.map((p) => (
              <button
                key={p}
                className="glass-card p-4 flex flex-col items-center gap-2 hover:bg-card-hover transition-colors"
              >
                <PlatformIcon platform={p} size={28} />
                <span className="text-sm capitalize">
                  {p.replace("_", " ")}
                </span>
                <span className="text-xs text-accent flex items-center gap-1">
                  <Plus size={12} /> {t("connect")}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
