-- YtBoost subscriptions: YouTube channels connected by users
CREATE TABLE IF NOT EXISTS ytboost_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    youtube_channel_id TEXT NOT NULL,
    channel_name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT now(),
    last_checked_at TIMESTAMPTZ,
    auto_distribute BOOLEAN DEFAULT false,
    target_platforms JSONB DEFAULT '[]',
    auto_comment_mode TEXT DEFAULT 'review',
    UNIQUE(user_id, youtube_channel_id)
);

CREATE INDEX IF NOT EXISTS idx_ytboost_subs_user ON ytboost_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_ytboost_subs_channel ON ytboost_subscriptions(youtube_channel_id);

-- YtBoost shorts: extracted short clips from long-form videos
CREATE TABLE IF NOT EXISTS ytboost_shorts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_video_id TEXT NOT NULL,
    source_channel_id TEXT NOT NULL,
    start_seconds INT,
    end_seconds INT,
    hook_line TEXT,
    suggested_title TEXT,
    suggested_hashtags JSONB DEFAULT '[]',
    reason TEXT,
    clip_file_url TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    approved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ytboost_shorts_user ON ytboost_shorts(user_id);
CREATE INDEX IF NOT EXISTS idx_ytboost_shorts_video ON ytboost_shorts(source_video_id);
CREATE INDEX IF NOT EXISTS idx_ytboost_shorts_status ON ytboost_shorts(status);

-- YtBoost channel tones: learned comment style for autopilot
CREATE TABLE IF NOT EXISTS ytboost_channel_tones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    youtube_channel_id TEXT NOT NULL,
    tone_profile JSONB DEFAULT '{}',
    sample_size INT DEFAULT 0,
    learned_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, youtube_channel_id)
);

CREATE INDEX IF NOT EXISTS idx_ytboost_tones_user ON ytboost_channel_tones(user_id);

-- Deduplication table for YouTube video notifications
CREATE TABLE IF NOT EXISTS ytboost_detected_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    video_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    detected_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, video_id)
);

CREATE INDEX IF NOT EXISTS idx_ytboost_detected_user ON ytboost_detected_videos(user_id);
