"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, RefreshCw, XCircle } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { PlatformIcon } from "@/components/platform-icon";

export default function PostDetailPage() {
  const t = useTranslations("posts");
  const tc = useTranslations("common");
  const params = useParams();
  const postId = params.id as string;

  // In production, fetch from API with SWR
  const post = {
    id: postId,
    content: "How to build a SaaS in 2026",
    title: "SaaS Building Guide",
    platforms: ["x_twitter", "linkedin"],
    status: "published",
    created_at: "2026-04-07T10:00:00Z",
    results: [
      {
        platform: "x_twitter",
        status: "published",
        url: "https://x.com/...",
        views: 1240,
        likes: 89,
      },
      {
        platform: "linkedin",
        status: "published",
        url: "https://linkedin.com/...",
        views: 560,
        likes: 42,
      },
    ],
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/posts" className="text-muted hover:text-text">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-2xl font-bold">{t("post_detail")}</h1>
      </div>

      {/* Content */}
      <div className="glass-card p-5">
        <h2 className="font-semibold mb-2">{post.title}</h2>
        <p className="text-muted-strong whitespace-pre-wrap">{post.content}</p>
        <div className="text-xs text-muted mt-3">
          {t("date")}: {new Date(post.created_at).toLocaleString()}
        </div>
      </div>

      {/* Platform Results */}
      <div className="glass-card">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="font-semibold">{t("platform_results")}</h2>
        </div>
        <div className="divide-y divide-border">
          {post.results.map((r) => (
            <div
              key={r.platform}
              className="px-5 py-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <PlatformIcon platform={r.platform} size={20} />
                <div>
                  <div className="text-sm font-medium capitalize">
                    {r.platform.replace("_", " ")}
                  </div>
                  <span className="text-xs text-success">{r.status}</span>
                </div>
              </div>
              <div className="flex items-center gap-6 text-sm text-muted">
                <span>{r.views.toLocaleString()} {t("views")}</span>
                <span>{r.likes.toLocaleString()} {t("likes")}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} /> {t("republish")}
        </button>
        <button className="btn-danger flex items-center gap-2">
          <XCircle size={14} /> {tc("cancel")}
        </button>
      </div>
    </div>
  );
}
