"use client";

import { Bell, LogOut, Menu } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";

interface Props {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: Props) {
  return (
    <header className="glass-card mx-4 mt-4 flex min-h-[72px] items-center justify-between px-4 sm:mx-6 sm:px-6 lg:mx-8">
      <button className="btn-ghost lg:hidden" onClick={onMenuClick} aria-label="Open navigation">
        <Menu size={22} />
      </button>

      <div className="hidden lg:block">
        <p className="pill">Operations cockpit</p>
        <h1 className="mt-2 text-2xl font-semibold text-text">ContentFlow Dashboard</h1>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <ThemeToggle />
        <LanguageSwitcher />

        <button className="btn-secondary relative min-w-[48px] px-0" aria-label="Notifications">
          <Bell size={20} />
          <span className="absolute right-3 top-3 h-2 w-2 rounded-full bg-accent-2" />
        </button>

        <div className="flex items-center gap-3 rounded-full border border-border/70 bg-card-hover/50 px-3 py-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-accent text-sm font-bold text-[#20110b]">
            CF
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-semibold text-text">Creator Ops</div>
            <div className="text-xs text-muted">Starter workspace</div>
          </div>
          <button className="btn-ghost min-w-[40px] px-0 text-muted hover:text-danger" aria-label="Log out">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
