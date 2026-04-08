"use client";

import {
  Youtube,
  Instagram,
  Linkedin,
  MessageCircle,
  Globe,
  type LucideIcon,
} from "lucide-react";

const icons: Record<string, LucideIcon> = {
  youtube: Youtube,
  instagram: Instagram,
  linkedin: Linkedin,
  line: MessageCircle,
  x_twitter: Globe,
  tiktok: Globe,
  medium: Globe,
  mastodon: Globe,
};

interface Props {
  platform: string;
  size?: number;
  className?: string;
}

export function PlatformIcon({ platform, size = 18, className }: Props) {
  const Icon = icons[platform.toLowerCase()] ?? Globe;
  return <Icon size={size} className={className} />;
}
