"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Save, Bell, Shield, Users } from "lucide-react";

export default function SettingsPage() {
  const t = useTranslations("settings");
  const [name, setName] = useState("User");
  const [email, setEmail] = useState("user@example.com");
  const [notifications, setNotifications] = useState({
    product_updates: true,
    billing: true,
    security: true,
    monthly_summary: true,
    webhook_alerts: true,
  });

  const notifLabels: Record<string, string> = {
    product_updates: t("product_updates"),
    billing: t("billing_alerts"),
    security: t("security_alerts"),
    monthly_summary: t("monthly_summary"),
    webhook_alerts: t("webhook_alerts"),
  };

  function toggleNotification(key: keyof typeof notifications) {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {/* Profile */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Shield size={18} className="text-accent" />
          <h2 className="font-semibold">{t("profile")}</h2>
        </div>
        <div>
          <label className="block text-sm text-muted mb-1">{t("name")}</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-sm text-muted mb-1">{t("email")}</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-sm text-muted mb-1">
            {t("change_password")}
          </label>
          <input
            type="password"
            placeholder={t("new_password")}
            className="w-full"
          />
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Save size={14} /> {t("save_changes")}
        </button>
      </div>

      {/* Notifications */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Bell size={18} className="text-accent" />
          <h2 className="font-semibold">{t("notifications")}</h2>
        </div>
        {Object.entries(notifications).map(([key, enabled]) => (
          <div key={key} className="flex items-center justify-between py-1">
            <span className="text-sm">
              {notifLabels[key] ?? key}
            </span>
            <button
              onClick={() =>
                toggleNotification(key as keyof typeof notifications)
              }
              className={`w-11 h-6 rounded-full transition-colors ${
                enabled ? "bg-accent" : "bg-border"
              }`}
            >
              <div
                className={`w-5 h-5 bg-white rounded-full transition-transform ${
                  enabled ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
        ))}
      </div>

      {/* Team */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Users size={18} className="text-accent" />
          <h2 className="font-semibold">{t("team")}</h2>
        </div>
        <p className="text-sm text-muted">{t("team_upgrade_msg")}</p>
        <button className="btn-secondary text-sm">{t("upgrade_to_invite")}</button>
      </div>
    </div>
  );
}
