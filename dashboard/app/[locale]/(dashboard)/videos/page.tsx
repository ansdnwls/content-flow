"use client";

import { useTranslations } from "next-intl";
import { Plus, Video, Clock, CheckCircle } from "lucide-react";
import { Link } from "@/i18n/navigation";

const DEMO_VIDEOS = [
  {
    id: "1",
    topic: "AI in Legal Industry",
    mode: "legal",
    status: "completed",
    created_at: "2026-04-07",
  },
  {
    id: "2",
    topic: "Philosophy of Consciousness",
    mode: "philosophy",
    status: "processing",
    created_at: "2026-04-06",
  },
  {
    id: "3",
    topic: "Breaking: Tech News Roundup",
    mode: "news",
    status: "completed",
    created_at: "2026-04-05",
  },
];

export default function VideosPage() {
  const t = useTranslations("videos");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <Link
          href="/videos/new"
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={16} /> {t("generate_video")}
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {DEMO_VIDEOS.map((v) => (
          <div key={v.id} className="glass-card p-5 space-y-3">
            <div className="flex items-start justify-between">
              <div className="p-2 rounded-lg bg-accent/10">
                <Video size={20} className="text-accent" />
              </div>
              {v.status === "completed" ? (
                <CheckCircle size={18} className="text-success" />
              ) : (
                <Clock size={18} className="text-warning animate-pulse" />
              )}
            </div>
            <h3 className="font-semibold">{v.topic}</h3>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted capitalize">{v.mode}</span>
              <span className="text-muted">{v.created_at}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
