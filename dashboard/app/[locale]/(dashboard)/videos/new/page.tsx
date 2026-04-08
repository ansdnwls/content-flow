"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Video } from "lucide-react";

const MODES = ["legal", "philosophy", "senior", "news", "mystery", "educational", "storytelling"];

const TEMPLATES = [
  { id: "cinematic", label: "Cinematic" },
  { id: "minimal", label: "Minimal" },
  { id: "dynamic", label: "Dynamic" },
  { id: "retro", label: "Retro" },
  { id: "neon", label: "Neon" },
];

export default function NewVideoPage() {
  const t = useTranslations("videos");
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState("legal");
  const [language, setLanguage] = useState("en");
  const [template, setTemplate] = useState("cinematic");
  const [autoPublish, setAutoPublish] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const apiKey = localStorage.getItem("cf_api_key") ?? "";
      const res = await fetch(`${API_URL}/api/v1/videos`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({
          topic,
          mode,
          language,
          template_id: template,
          auto_publish: autoPublish,
        }),
      });
      if (!res.ok) throw new Error("Failed to create video");
      router.push("/videos");
    } catch {
      alert("Failed to generate video");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent">
          <Video size={22} />
        </div>
        <div>
          <h1 className="section-title">{t("generate_video")}</h1>
          <p className="section-subtitle">{t("subtitle")}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="glass-card p-5 sm:p-6">
          <div className="grid gap-5">
            <div className="form-field">
              <label className="form-field__label">{t("topic")}</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder={t("topic_placeholder")}
                required
                className="w-full"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="form-field">
                <label className="form-field__label">{t("mode")}</label>
                <select value={mode} onChange={(e) => setMode(e.target.value)} className="w-full">
                  {MODES.map((m) => (
                    <option key={m} value={m}>
                      {m.charAt(0).toUpperCase() + m.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label className="form-field__label">{t("language")}</label>
                <select value={language} onChange={(e) => setLanguage(e.target.value)} className="w-full">
                  <option value="en">English</option>
                  <option value="ko">Korean</option>
                  <option value="ja">Japanese</option>
                  <option value="es">Spanish</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div className="glass-card p-5 sm:p-6">
          <div className="mb-4">
            <div className="pill">{t("template")}</div>
            <p className="section-subtitle">{t("template_desc")}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {TEMPLATES.map((tpl) => (
              <button key={tpl.id} type="button" onClick={() => setTemplate(tpl.id)} className={`toggle-chip justify-center ${template === tpl.id ? "is-active" : ""}`}>
                {tpl.label}
              </button>
            ))}
          </div>
        </div>

        <div className="glass-card p-5 sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="pill">{t("auto_publish")}</div>
              <p className="section-subtitle">{t("auto_publish_desc")}</p>
            </div>
            <button
              type="button"
              onClick={() => setAutoPublish(!autoPublish)}
              className={`relative inline-flex h-8 w-14 items-center rounded-full border transition-colors ${
                autoPublish ? "border-accent-2/80 bg-accent/20" : "border-border/70 bg-card-hover/70"
              }`}
              aria-pressed={autoPublish}
              aria-label="Toggle auto-publish"
            >
              <span
                className={`absolute h-6 w-6 rounded-full bg-gradient-accent transition-transform ${
                  autoPublish ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>

        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading ? t("generating") : t("generate")}
        </button>
      </form>
    </div>
  );
}
