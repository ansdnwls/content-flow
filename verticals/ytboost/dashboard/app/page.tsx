import config from "../../config.json";
import { DistributionMap, ViralScore } from "@contentflow/ui/widgets";
import { engine } from "../lib/api";
import type { YtBoostChannel, PendingComment } from "../lib/api";

async function getChannels(): Promise<readonly YtBoostChannel[]> {
  const res = await engine.listChannels();
  return res.data ?? [];
}

async function getPendingComments(): Promise<{
  data: readonly PendingComment[];
  total: number;
}> {
  const res = await engine.listPendingComments();
  return res.data ?? { data: [], total: 0 };
}

function ChannelList({ channels }: { channels: readonly YtBoostChannel[] }) {
  if (channels.length === 0) {
    return (
      <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
        <h3 className="font-semibold mb-4 text-[var(--color-text)]">YouTube Channels</h3>
        <p className="text-[var(--color-text)]/50 text-sm">
          No channels connected yet. Connect your YouTube channel to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">
        YouTube Channels ({channels.length})
      </h3>
      <ul className="space-y-3">
        {channels.map((ch) => (
          <li
            key={ch.id}
            className="flex items-center justify-between rounded-lg bg-[var(--color-bg)] p-3"
          >
            <div>
              <p className="font-medium text-[var(--color-text)]">
                {ch.channel_name ?? ch.youtube_channel_id}
              </p>
              <p className="text-xs text-[var(--color-text)]/50">
                {ch.auto_distribute ? "Auto-distribute ON" : "Manual"} · {ch.auto_comment_mode}
              </p>
            </div>
            <span className="text-xs px-2 py-1 rounded bg-[var(--color-primary)]/20 text-[var(--color-primary)]">
              {ch.target_platforms.length} platforms
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PendingCommentsList({
  comments,
}: {
  comments: { data: readonly PendingComment[]; total: number };
}) {
  if (comments.total === 0) {
    return (
      <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
        <h3 className="font-semibold mb-4 text-[var(--color-text)]">Pending Replies</h3>
        <p className="text-[var(--color-text)]/50 text-sm">No pending comment replies</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">
        Pending Replies ({comments.total})
      </h3>
      <ul className="space-y-3">
        {comments.data.slice(0, 5).map((c) => (
          <li key={c.id} className="rounded-lg bg-[var(--color-bg)] p-3">
            <p className="text-sm text-[var(--color-text)]">
              <span className="font-medium">{c.author_name}:</span> {c.text}
            </p>
            {c.ai_reply && (
              <p className="text-xs text-[var(--color-primary)] mt-1">
                AI reply: {c.ai_reply.slice(0, 80)}...
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function DashboardHome() {
  let channels: readonly YtBoostChannel[] = [];
  let pendingComments: { data: readonly PendingComment[]; total: number } = {
    data: [],
    total: 0,
  };

  try {
    [channels, pendingComments] = await Promise.all([
      getChannels(),
      getPendingComments(),
    ]);
  } catch {
    // API unavailable — render with empty data
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6 text-[var(--color-text)]">
        Welcome to {config.name}
      </h1>
      <div className="grid md:grid-cols-2 gap-6">
        <ChannelList channels={channels} />
        <PendingCommentsList comments={pendingComments} />
        <DistributionMap key="distribution_map" />
        <ViralScore key="viral_score" />
      </div>
    </div>
  );
}
