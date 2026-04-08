"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Webhook,
} from "lucide-react";

interface WebhookEntry {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  last_status: number | null;
  failures: number;
}

const DEMO_WEBHOOKS: WebhookEntry[] = [
  {
    id: "1",
    url: "https://example.com/webhook/posts",
    events: ["post.created", "post.published"],
    active: true,
    last_status: 200,
    failures: 0,
  },
  {
    id: "2",
    url: "https://example.com/webhook/all",
    events: ["*"],
    active: false,
    last_status: 500,
    failures: 5,
  },
];

export default function WebhooksPage() {
  const t = useTranslations("webhooks");
  const tc = useTranslations("common");
  const [showAdd, setShowAdd] = useState(false);
  const [newUrl, setNewUrl] = useState("");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={16} /> {t("add_webhook")}
        </button>
      </div>

      {showAdd && (
        <div className="glass-card p-5 space-y-3">
          <label className="block text-sm text-muted">{t("endpoint_url")}</label>
          <div className="flex gap-2">
            <input
              type="url"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder={t("url_placeholder")}
              className="flex-1"
            />
            <button className="btn-primary">{tc("save")}</button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {DEMO_WEBHOOKS.map((wh) => (
          <div key={wh.id} className="glass-card p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <Webhook size={20} className="text-accent" />
                <div>
                  <div className="text-sm font-medium font-mono">{wh.url}</div>
                  <div className="text-xs text-muted mt-1">
                    {t("events")}: {wh.events.join(", ")}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {wh.active ? (
                  <CheckCircle size={16} className="text-success" />
                ) : (
                  <XCircle size={16} className="text-danger" />
                )}
                <button className="text-muted hover:text-accent-2">
                  <RefreshCw size={14} />
                </button>
                <button className="text-muted hover:text-danger">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            {wh.failures > 0 && (
              <div className="mt-2 text-xs text-danger bg-danger/10 rounded-lg p-2">
                {t("consecutive_failures", { count: wh.failures, status: wh.last_status ?? 0 })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
