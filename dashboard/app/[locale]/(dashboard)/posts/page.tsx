"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { ArrowUpRight, FileText, Plus, Search } from "lucide-react";
import { Link } from "@/i18n/navigation";

import { PlatformIcon } from "@/components/platform-icon";

interface Post {
  id: string;
  content: string;
  platforms: string[];
  status: string;
  created_at: string;
}

const DEMO_POSTS: Post[] = [
  {
    id: "1",
    content: "How to build a SaaS in 2026",
    platforms: ["x_twitter", "linkedin"],
    status: "published",
    created_at: "2026-04-07",
  },
  {
    id: "2",
    content: "Thread about content automation tools",
    platforms: ["x_twitter"],
    status: "scheduled",
    created_at: "2026-04-06",
  },
  {
    id: "3",
    content: "New product launch announcement",
    platforms: ["instagram", "tiktok", "youtube"],
    status: "failed",
    created_at: "2026-04-05",
  },
];

export default function PostsPage() {
  const t = useTranslations("posts");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  function statusBadge(status: string) {
    const colors: Record<string, string> = {
      published: "bg-success/20 text-success",
      pending: "bg-warning/20 text-warning",
      scheduled: "bg-accent-2/20 text-accent-2",
      failed: "bg-danger/20 text-danger",
    };
    return <span className={`status-pill ${colors[status] ?? "bg-muted/20 text-muted"}`}>{t(status as "published" | "scheduled" | "pending" | "failed")}</span>;
  }

  const filtered = DEMO_POSTS.filter((p) => {
    if (statusFilter !== "all" && p.status !== statusFilter) return false;
    if (search && !p.content.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="section-title">{t("title")}</h1>
          <p className="section-subtitle">{t("subtitle")}</p>
        </div>
        <Link href="/posts/new" className="btn-primary">
          <Plus size={16} /> {t("new_post")}
        </Link>
      </div>

      <div className="glass-card p-4 sm:p-5">
        <div className="grid gap-3 lg:grid-cols-[1fr_180px]">
          <div className="relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder={t("search_posts")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-11"
              aria-label={t("search_posts")}
            />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label={t("status")}>
            <option value="all">{t("all_status")}</option>
            <option value="published">{t("published")}</option>
            <option value="scheduled">{t("scheduled")}</option>
            <option value="pending">{t("pending")}</option>
            <option value="failed">{t("failed")}</option>
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-illustration">
          <div>
            <Image src="/illustrations/empty-posts.svg" alt="" width={240} height={160} />
            <h2 className="text-2xl font-semibold text-text">{t("no_results")}</h2>
            <p className="mt-2 max-w-md text-sm text-muted">{t("no_results_desc")}</p>
          </div>
        </div>
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>{t("content")}</th>
                <th>{t("platforms")}</th>
                <th>{t("status")}</th>
                <th>{t("date")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((post) => (
                <tr key={post.id}>
                  <td>
                    <Link href={`/posts/${post.id}`} className="flex items-center gap-3 hover:text-accent">
                      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-card-hover/60">
                        <FileText size={16} className="text-accent" />
                      </span>
                      <span className="flex items-center gap-2">
                        <span>{post.content}</span>
                        <ArrowUpRight size={14} className="text-muted" />
                      </span>
                    </Link>
                  </td>
                  <td>
                    <div className="flex gap-1.5">
                      {post.platforms.map((p) => (
                        <span key={p} className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/60 bg-card-hover/50">
                          <PlatformIcon platform={p} size={16} />
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>{statusBadge(post.status)}</td>
                  <td className="text-muted">{post.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
