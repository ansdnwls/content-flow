import React from "react";
import { PLATFORM_LABELS } from "@contentflow/config";

interface DistributionItem {
  readonly platform: string;
  readonly count: number;
}

interface DistributionMapProps {
  readonly data?: readonly DistributionItem[];
}

const MOCK_DATA: DistributionItem[] = [
  { platform: "youtube", count: 24 },
  { platform: "tiktok", count: 18 },
  { platform: "instagram", count: 15 },
  { platform: "x", count: 12 },
  { platform: "facebook", count: 8 },
];

export function DistributionMap({ data = MOCK_DATA }: DistributionMapProps) {
  const max = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Distribution</h3>
      <div className="space-y-3">
        {data.map((item) => (
          <div key={item.platform} className="flex items-center gap-3">
            <span className="text-sm w-24 text-[var(--color-text)]/70 truncate">
              {PLATFORM_LABELS[item.platform] ?? item.platform}
            </span>
            <div className="flex-1 h-6 bg-[var(--color-text)]/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--color-primary)] rounded-full transition-all"
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-[var(--color-text)] w-8 text-right">
              {item.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
