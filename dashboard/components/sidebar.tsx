"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3,
  CreditCard,
  FileText,
  Home,
  Key,
  Settings,
  Users,
  Video,
  Webhook,
  X,
  Zap,
} from "lucide-react";

import { riseIn } from "@/lib/animations";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", icon: Home, key: "home" },
  { href: "/posts", icon: FileText, key: "posts" },
  { href: "/videos", icon: Video, key: "videos" },
  { href: "/accounts", icon: Users, key: "accounts" },
  { href: "/analytics", icon: BarChart3, key: "analytics" },
  { href: "/webhooks", icon: Webhook, key: "webhooks" },
  { href: "/api-keys", icon: Key, key: "api_keys" },
  { href: "/billing", icon: CreditCard, key: "billing" },
  { href: "/settings", icon: Settings, key: "settings" },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: Props) {
  const pathname = usePathname();
  const t = useTranslations();

  return (
    <>
      <AnimatePresence>
        {open ? (
          <motion.button
            type="button"
            className="fixed inset-0 z-40 bg-black/55 lg:hidden"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            aria-label="Close navigation overlay"
          />
        ) : null}
      </AnimatePresence>

      <aside
        className={cn(
          "sidebar-shell flex flex-col transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-20 items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-accent text-[#20110b] shadow-[0_18px_30px_rgba(255,107,53,0.22)]">
              <Zap size={20} />
            </div>
            <div>
              <div className="text-lg font-semibold gradient-text">ContentFlow</div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted">{t("nav.signal_engine")}</div>
            </div>
          </Link>
          <button className="btn-ghost min-w-[40px] px-0 lg:hidden" onClick={onClose} aria-label="Close navigation">
            <X size={20} />
          </button>
        </div>

        <div className="px-4">
          <div className="glass-card--soft rounded-[24px] border p-4">
            <div className="pill">{t("nav.current_plan")}</div>
            <div className="mt-3 text-3xl font-semibold text-text">{t("billing.free")}</div>
            <p className="mt-2 text-sm text-muted">{t("dashboard.posts_used", { used: 42, total: 100 })}</p>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-card">
              <div className="h-full w-[42%] rounded-full bg-gradient-accent" />
            </div>
            <Link href="/billing" className="mt-4 inline-flex text-sm font-semibold text-accent-2">
              {t("nav.upgrade")}
            </Link>
          </div>
        </div>

        <nav className="flex-1 space-y-2 overflow-y-auto px-4 py-5">
          {NAV_ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <motion.div key={item.href} variants={riseIn} initial="initial" animate="animate">
                <Link href={item.href} onClick={onClose} className={cn("sidebar-link", active && "is-active")}>
                  <item.icon size={18} />
                  {t(`nav.${item.key}`)}
                </Link>
              </motion.div>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
