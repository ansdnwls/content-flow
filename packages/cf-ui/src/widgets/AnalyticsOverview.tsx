import React from "react";

interface Stat {
  readonly label: string;
  readonly value: string | number;
  readonly change?: string;
}

interface AnalyticsOverviewProps {
  readonly stats?: readonly Stat[];
}

const DEFAULT_STATS: Stat[] = [
  { label: "Total Posts", value: 0, change: "+0" },
  { label: "Total Reach", value: 0, change: "+0" },
  { label: "Engagement", value: "0%", change: "+0%" },
  { label: "Platforms", value: 0 },
];

export function AnalyticsOverview({ stats = DEFAULT_STATS }: AnalyticsOverviewProps) {
  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Analytics</h3>
      <div className="grid grid-cols-2 gap-4">
        {stats.map((stat) => (
          <div key={stat.label}>
            <p className="text-xs text-[var(--color-text)]/50 uppercase tracking-wide">
              {stat.label}
            </p>
            <p className="text-2xl font-bold text-[var(--color-text)]">{stat.value}</p>
            {stat.change && (
              <p className="text-xs text-green-400">{stat.change}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
