"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Clock, Send } from "lucide-react";

import { PlatformIcon } from "@/components/platform-icon";

const PLATFORMS = ["youtube", "tiktok", "instagram", "x_twitter", "linkedin", "medium", "mastodon", "line"];

export default function NewPostPage() {
  const t = useTranslations("posts");
  const router = useRouter();
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [scheduleMode, setScheduleMode] = useState<"now" | "scheduled">("now");
  const [scheduledFor, setScheduledFor] = useState("");
  const [loading, setLoading] = useState(false);

  function togglePlatform(p: string) {
    setSelectedPlatforms((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const apiKey = localStorage.getItem("cf_api_key") ?? "";
      const res = await fetch(`${API_URL}/api/v1/posts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({
          content,
          title: title || undefined,
          platforms: selectedPlatforms,
          scheduled_for: scheduleMode === "scheduled" ? scheduledFor : undefined,
        }),
      });
      if (!res.ok) throw new Error("Failed to create post");
      router.push("/posts");
    } catch {
      alert("Failed to create post");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="section-title">{t("new_post")}</h1>
        <p className="section-subtitle">{t("new_post_subtitle")}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="glass-card p-5 sm:p-6">
          <div className="grid gap-5">
            <div className="form-field">
              <label className="form-field__label">{t("post_title")}</label>
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t("title_placeholder")} className="w-full" />
            </div>
            <div className="form-field">
              <label className="form-field__label">{t("post_content")}</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder={t("content_placeholder")}
                rows={8}
                required
                className="w-full resize-y"
              />
            </div>
          </div>
        </div>

        <div className="glass-card p-5 sm:p-6">
          <div className="mb-4">
            <div className="pill">{t("platform_routing")}</div>
            <p className="section-subtitle">{t("platform_routing_desc")}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {PLATFORMS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => togglePlatform(p)}
                className={`toggle-chip justify-start ${selectedPlatforms.includes(p) ? "is-active" : ""}`}
              >
                <PlatformIcon platform={p} size={16} />
                {p.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        <div className="glass-card p-5 sm:p-6">
          <div className="mb-4">
            <div className="pill">{t("timing")}</div>
            <p className="section-subtitle">{t("timing_desc")}</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => setScheduleMode("now")} className={`toggle-chip ${scheduleMode === "now" ? "is-active" : ""}`}>
              <Send size={14} /> {t("publish_now")}
            </button>
            <button
              type="button"
              onClick={() => setScheduleMode("scheduled")}
              className={`toggle-chip ${scheduleMode === "scheduled" ? "is-active" : ""}`}
            >
              <Clock size={14} /> {t("schedule")}
            </button>
          </div>
          {scheduleMode === "scheduled" ? (
            <div className="mt-4">
              <label className="form-field__label">{t("scheduled_time")}</label>
              <input type="datetime-local" value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} required className="w-full" />
            </div>
          ) : null}
        </div>

        <button type="submit" disabled={loading || selectedPlatforms.length === 0} className="btn-primary w-full">
          {loading ? t("creating") : scheduleMode === "now" ? t("publish_post") : t("schedule_post")}
        </button>
      </form>
    </div>
  );
}
