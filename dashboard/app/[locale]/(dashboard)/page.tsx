"use client";

import { useTranslations } from "next-intl";
import { motion } from "framer-motion";
import { Activity, ArrowUpRight, FileText, Link2, Plus, Users, Video, Zap } from "lucide-react";
import { Link } from "@/i18n/navigation";

import { StatCard } from "@/components/stat-card";
import { pageTransition, riseIn, staggerContainer } from "@/lib/animations";

const RECENT: {
  id: string;
  type: string;
  title: string;
  platform: string;
  status: string;
  time: string;
}[] = [
  {
    id: "1",
    type: "post",
    title: "How to build a SaaS in 2026",
    platform: "x_twitter",
    status: "published",
    time: "2 hours ago",
  },
  {
    id: "2",
    type: "video",
    title: "AI Legal Explainer #12",
    platform: "youtube",
    status: "processing",
    time: "4 hours ago",
  },
  {
    id: "3",
    type: "post",
    title: "Thread about content automation",
    platform: "linkedin",
    status: "scheduled",
    time: "6 hours ago",
  },
];

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    published: "bg-success/20 text-success",
    processing: "bg-warning/20 text-warning",
    scheduled: "bg-accent-2/20 text-accent-2",
    failed: "bg-danger/20 text-danger",
  };
  return (
    <span className={`status-pill ${colors[status] ?? "bg-muted/20 text-muted"}`}>
      {status}
    </span>
  );
}

export default function DashboardHome() {
  const t = useTranslations("dashboard");

  const stats = [
    { title: t("posts_this_month"), value: 42, icon: FileText, change: 12 },
    { title: t("videos_generated"), value: 7, icon: Video, change: 40 },
    { title: t("api_calls"), value: 1_280, icon: Activity, change: -3 },
    { title: t("active_accounts"), value: 5, icon: Users, change: 25 },
  ];

  return (
    <motion.div className="space-y-6" variants={pageTransition} initial="initial" animate="animate">
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="glass-card p-6 sm:p-7">
          <div className="pill">{t("control_room")}</div>
          <h1 className="mt-4 text-4xl font-semibold text-text sm:text-5xl">{t("ship_headline")}</h1>
          <p className="section-subtitle max-w-2xl">{t("ship_desc")}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/posts/new" className="btn-primary">
              <Plus size={16} /> {t("new_post")}
            </Link>
            <Link href="/accounts" className="btn-secondary">
              <Link2 size={16} /> {t("connect_account")}
            </Link>
          </div>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            <div className="glass-card--soft rounded-[24px] border p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">{t("burst_velocity")}</div>
              <div className="mt-3 text-2xl font-semibold text-text">21 {t("outputs")}</div>
            </div>
            <div className="glass-card--soft rounded-[24px] border p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">{t("reply_coverage")}</div>
              <div className="mt-3 text-2xl font-semibold text-text">92%</div>
            </div>
            <div className="glass-card--soft rounded-[24px] border p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">{t("regional_mix")}</div>
              <div className="mt-3 text-2xl font-semibold text-text">KR + JP ready</div>
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="pill">{t("signal_monitor")}</div>
              <h2 className="mt-4 text-2xl font-semibold text-text">{t("workflow_health")}</h2>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent">
              <Zap size={20} />
            </div>
          </div>
          <div className="mt-6 space-y-3">
            <div className="rounded-[22px] border border-border/50 bg-card-hover/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">{t("plan_usage")}</span>
                <span className="text-sm text-muted">{t("posts_used", { used: 42, total: 100 })}</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-card">
                <div className="h-full w-[42%] rounded-full bg-gradient-accent" />
              </div>
            </div>
            <div className="rounded-[22px] border border-border/50 bg-card-hover/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">{t("comment_queue")}</span>
                <span className="text-sm text-success">{t("healthy")}</span>
              </div>
              <p className="mt-2 text-sm text-muted">11 threads pending review, 38 auto-drafts ready.</p>
            </div>
            <div className="rounded-[22px] border border-border/50 bg-card-hover/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">{t("regional_endpoints")}</span>
                <span className="text-sm text-accent-2">{t("online")}</span>
              </div>
              <p className="mt-2 text-sm text-muted">Naver Blog, Tistory, Kakao, LINE, and note.com are synced.</p>
            </div>
          </div>
        </div>
      </div>

      <motion.div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" variants={staggerContainer} initial="initial" animate="animate">
        {stats.map((s) => (
          <motion.div key={s.title} variants={riseIn}>
            <StatCard {...s} />
          </motion.div>
        ))}
      </motion.div>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.92fr]">
        <div className="glass-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-border/50 px-5 py-4">
            <div>
              <h2 className="text-xl font-semibold text-text">{t("recent_activity")}</h2>
              <p className="mt-1 text-sm text-muted">{t("recent_activity_desc")}</p>
            </div>
            <Link href="/posts" className="btn-ghost">
              {t("view_all")} <ArrowUpRight size={16} />
            </Link>
          </div>
          <div className="divide-y divide-border/50">
            {RECENT.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-card-hover/60">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-card-hover/70">
                    {item.type === "post" ? (
                      <FileText size={18} className="text-accent" />
                    ) : (
                      <Video size={18} className="text-accent-2" />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text">{item.title}</div>
                    <div className="text-xs uppercase tracking-[0.14em] text-muted">{item.platform}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {statusBadge(item.status)}
                  <span className="text-xs text-muted">{item.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-5">
          <div className="pill">{t("todays_focus")}</div>
          <h2 className="mt-4 text-2xl font-semibold text-text">{t("next_move")}</h2>
          <div className="mt-5 space-y-3">
            <div className="rounded-[22px] border border-border/50 bg-card-hover/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">Finish launch burst</span>
                <span className="text-success">In progress</span>
              </div>
              <p className="mt-2 text-sm text-muted">3 regional channels still need localized copy approval.</p>
            </div>
            <div className="rounded-[22px] border border-border/50 bg-card-hover/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">Top reply queue</span>
                <span className="text-warning">11 pending</span>
              </div>
              <p className="mt-2 text-sm text-muted">Autopilot drafted answers for the five highest-signal threads.</p>
            </div>
            <div className="rounded-[22px] border border-border/50 bg-card-hover/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">API drift check</span>
                <span className="text-accent-2">Stable</span>
              </div>
              <p className="mt-2 text-sm text-muted">No publish or webhook failures detected in the last 24 hours.</p>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
