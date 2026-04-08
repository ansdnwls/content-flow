import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(date));
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

export function platformColor(platform: string): string {
  const colors: Record<string, string> = {
    youtube: "#FF0000",
    tiktok: "#00F2EA",
    instagram: "#E1306C",
    x_twitter: "#1DA1F2",
    linkedin: "#0A66C2",
    medium: "#00AB6C",
    mastodon: "#6364FF",
    line: "#06C755",
  };
  return colors[platform.toLowerCase()] ?? "#9a6bff";
}
