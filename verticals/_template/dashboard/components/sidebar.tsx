"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import config from "../../config.json";

const NAV_MAP: Record<string, { label: string; href: string; icon: string }> = {
  home: { label: "Home", href: "/", icon: "\u2302" },
  posts: { label: "Posts", href: "/posts", icon: "\u270E" },
  videos: { label: "Videos", href: "/videos", icon: "\u25B6" },
  shorts: { label: "Shorts", href: "/shorts", icon: "\u23F1" },
  distribution: { label: "Distribution", href: "/distribution", icon: "\u21C4" },
  comments: { label: "Comments", href: "/comments", icon: "\u2709" },
  analytics: { label: "Analytics", href: "/analytics", icon: "\u2191" },
  accounts: { label: "Accounts", href: "/accounts", icon: "\u2B55" },
  products: { label: "Products", href: "/products", icon: "\u2606" },
  inventory: { label: "Inventory", href: "/inventory", icon: "\u2630" },
  settings: { label: "Settings", href: "/settings", icon: "\u2699" },
};

export function Sidebar() {
  const pathname = usePathname();
  const navItems = config.dashboard.nav
    .filter((key) => !config.features.hide.includes(key))
    .map((key) => NAV_MAP[key])
    .filter(Boolean);

  return (
    <aside className="w-64 border-r border-[var(--color-text)]/10 bg-[var(--color-secondary)] flex flex-col">
      <div className="p-6">
        <h1 className="text-xl font-bold text-[var(--color-text)]">{config.name}</h1>
        <p className="text-xs text-[var(--color-text)]/50 mt-1">{config.tagline}</p>
      </div>
      <nav className="flex-1 px-3">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 text-sm transition-colors ${
                isActive
                  ? "bg-[var(--color-primary)] text-white"
                  : "text-[var(--color-text)]/70 hover:bg-[var(--color-text)]/5"
              }`}
            >
              <span className="text-lg">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
