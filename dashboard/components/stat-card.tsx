"use client";

import { type LucideIcon } from "lucide-react";

import { cn, formatNumber } from "@/lib/utils";

interface Props {
  title: string;
  value: number;
  icon: LucideIcon;
  change?: number;
  className?: string;
}

export function StatCard({ title, value, icon: Icon, change, className }: Props) {
  return (
    <div className={cn("metric-card", className)}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <span className="pill">{title}</span>
          <div className="metric-card__value mt-4">{formatNumber(value)}</div>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent/10 text-accent">
          <Icon size={18} />
        </div>
      </div>
      {change !== undefined && (
        <div className={cn("text-xs font-semibold uppercase tracking-[0.14em]", change >= 0 ? "text-success" : "text-danger")}>
          {change >= 0 ? "+" : ""}
          {change}% from last month
        </div>
      )}
      <div className="metric-card__spark mt-4">
        <div className="metric-card__spark-line" />
      </div>
    </div>
  );
}
