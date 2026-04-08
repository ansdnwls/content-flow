"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { EmptyState } from "@/components/empty-state";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from "recharts";
import { formatNumber } from "@/lib/utils";

const DAILY_POSTS = [
  { date: "Apr 1", posts: 5 },
  { date: "Apr 2", posts: 8 },
  { date: "Apr 3", posts: 3 },
  { date: "Apr 4", posts: 12 },
  { date: "Apr 5", posts: 7 },
  { date: "Apr 6", posts: 9 },
  { date: "Apr 7", posts: 6 },
];

const PLATFORM_DIST = [
  { name: "YouTube", value: 35 },
  { name: "Twitter", value: 28 },
  { name: "LinkedIn", value: 20 },
  { name: "Instagram", value: 12 },
  { name: "TikTok", value: 5 },
];

const VIEWS_DATA = [
  { date: "Apr 1", views: 1200, likes: 89 },
  { date: "Apr 2", views: 1800, likes: 120 },
  { date: "Apr 3", views: 900, likes: 65 },
  { date: "Apr 4", views: 2400, likes: 180 },
  { date: "Apr 5", views: 1600, likes: 110 },
  { date: "Apr 6", views: 2100, likes: 150 },
  { date: "Apr 7", views: 1900, likes: 130 },
];

const COLORS = ["#9a6bff", "#4ab8ff", "#76f6c8", "#ff6b6b", "#ffb84d"];

const TOP_POSTS = [
  { title: "How to build a SaaS", views: 4200, likes: 312 },
  { title: "AI Content Strategy", views: 3100, likes: 245 },
  { title: "Thread: Automation Tips", views: 2800, likes: 198 },
  { title: "Product Launch Post", views: 2200, likes: 167 },
  { title: "Weekly Tech Roundup", views: 1900, likes: 134 },
];

export default function AnalyticsPage() {
  const t = useTranslations("analytics");
  const [period, setPeriod] = useState("7d");

  const periodLabels: Record<string, string> = {
    "7d": t("last_7_days"),
    "30d": t("last_30_days"),
    "90d": t("last_90_days"),
  };

  if (DAILY_POSTS.length === 0) {
    return (
      <EmptyState
        title="Analytics are still warming up"
        description="Data starts filling in after the first publish burst lands. Once the system sees traffic, the charts will come alive."
        image="/illustrations/empty-analytics.svg"
        actionLabel="Create a post"
        actionHref="/en/posts/new"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <div className="flex gap-1 bg-card rounded-lg p-1">
          {["7d", "30d", "90d"].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                period === p
                  ? "bg-accent/20 text-accent"
                  : "text-muted hover:text-text"
              }`}
            >
              {periodLabels[p]}
            </button>
          ))}
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Daily posts */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-medium text-muted mb-4">{t("daily_posts")}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={DAILY_POSTS}>
              <XAxis dataKey="date" stroke="#aab3d8" fontSize={12} />
              <YAxis stroke="#aab3d8" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0c0f23",
                  border: "1px solid rgba(151,164,255,0.22)",
                  borderRadius: "8px",
                }}
              />
              <Bar dataKey="posts" fill="#9a6bff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Platform distribution */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-medium text-muted mb-4">
            {t("platform_distribution")}
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={PLATFORM_DIST}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                label={({ name, percent }) =>
                  `${name} ${(percent * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {PLATFORM_DIST.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Views & Likes chart */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-medium text-muted mb-4">
          {t("views_and_likes")}
        </h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={VIEWS_DATA}>
            <XAxis dataKey="date" stroke="#aab3d8" fontSize={12} />
            <YAxis stroke="#aab3d8" fontSize={12} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#0c0f23",
                border: "1px solid rgba(151,164,255,0.22)",
                borderRadius: "8px",
              }}
            />
            <Line
              type="monotone"
              dataKey="views"
              stroke="#4ab8ff"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="likes"
              stroke="#9a6bff"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Top Posts */}
      <div className="glass-card">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="font-semibold">{t("top_posts")}</h3>
        </div>
        <div className="divide-y divide-border">
          {TOP_POSTS.map((post, i) => (
            <div
              key={i}
              className="px-5 py-3 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted w-6">#{i + 1}</span>
                <span className="text-sm font-medium">{post.title}</span>
              </div>
              <div className="flex gap-4 text-sm text-muted">
                <span>{formatNumber(post.views)} {t("views")}</span>
                <span>{formatNumber(post.likes)} {t("likes")}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
