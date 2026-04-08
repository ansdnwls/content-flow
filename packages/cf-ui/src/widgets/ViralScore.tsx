import React from "react";

interface ViralScoreProps {
  readonly score?: number;
  readonly trend?: "up" | "down" | "stable";
  readonly label?: string;
}

export function ViralScore({
  score = 72,
  trend = "up",
  label = "Viral Score",
}: ViralScoreProps) {
  const trendIcon = trend === "up" ? "\u2191" : trend === "down" ? "\u2193" : "\u2192";
  const trendColor =
    trend === "up"
      ? "text-green-500"
      : trend === "down"
        ? "text-red-500"
        : "text-yellow-500";

  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-2 text-[var(--color-text)]">{label}</h3>
      <div className="flex items-end gap-3">
        <span className="text-4xl font-bold text-[var(--color-primary)]">{score}</span>
        <span className={`text-xl ${trendColor} mb-1`}>{trendIcon}</span>
      </div>
      <p className="text-sm text-[var(--color-text)]/50 mt-2">out of 100</p>
    </div>
  );
}
