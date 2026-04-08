import React from "react";

interface Post {
  readonly id: string;
  readonly title: string;
  readonly platform: string;
  readonly status: "published" | "scheduled" | "draft";
  readonly date: string;
}

interface RecentPostsProps {
  readonly posts?: readonly Post[];
}

const STATUS_STYLES: Record<string, string> = {
  published: "bg-green-500/20 text-green-400",
  scheduled: "bg-blue-500/20 text-blue-400",
  draft: "bg-gray-500/20 text-gray-400",
};

export function RecentPosts({ posts = [] }: RecentPostsProps) {
  return (
    <div className="rounded-xl bg-[var(--color-text)]/5 p-6">
      <h3 className="font-semibold mb-4 text-[var(--color-text)]">Recent Posts</h3>
      {posts.length === 0 ? (
        <p className="text-[var(--color-text)]/50 text-sm">No posts yet</p>
      ) : (
        <div className="space-y-3">
          {posts.slice(0, 5).map((post) => (
            <div
              key={post.id}
              className="flex items-center justify-between gap-3"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--color-text)] truncate">
                  {post.title}
                </p>
                <p className="text-xs text-[var(--color-text)]/50">{post.date}</p>
              </div>
              <span
                className={`text-xs px-2 py-1 rounded-full ${STATUS_STYLES[post.status] ?? ""}`}
              >
                {post.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
