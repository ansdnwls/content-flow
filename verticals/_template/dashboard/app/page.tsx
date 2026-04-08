import config from "../../config.json";
import { DistributionMap, ViralScore, RecentPosts, AnalyticsOverview } from "@contentflow/ui/widgets";

const WIDGET_MAP: Record<string, React.ReactNode> = {
  distribution_map: <DistributionMap key="distribution_map" />,
  viral_score_trending: <ViralScore key="viral_score" />,
  recent_posts: <RecentPosts key="recent_posts" />,
  analytics_overview: <AnalyticsOverview key="analytics_overview" />,
  youtube_channel_stats: (
    <div key="youtube_stats" className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">YouTube Channel</h3>
      <p className="text-[var(--color-text)]/50 text-sm">Connect your YouTube channel to see stats</p>
    </div>
  ),
  recent_shorts_generated: (
    <div key="shorts_gen" className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Recent Shorts</h3>
      <p className="text-[var(--color-text)]/50 text-sm">No shorts generated yet</p>
    </div>
  ),
  shop_inventory: (
    <div key="shop_inv" className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Inventory</h3>
      <p className="text-[var(--color-text)]/50 text-sm">Connect your shop to see inventory</p>
    </div>
  ),
  price_alerts: (
    <div key="price_alerts" className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Price Alerts</h3>
      <p className="text-[var(--color-text)]/50 text-sm">No active alerts</p>
    </div>
  ),
};

export default function DashboardHome() {
  const widgets = config.dashboard.home_widgets
    .map((key) => WIDGET_MAP[key])
    .filter(Boolean);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6 text-[var(--color-text)]">
        Welcome to {config.name}
      </h1>
      <div className="grid md:grid-cols-2 gap-6">
        {widgets}
      </div>
    </div>
  );
}
