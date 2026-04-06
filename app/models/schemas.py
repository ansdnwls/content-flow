"""
ContentFlow DB Schema — 7 tables for Supabase (PostgreSQL).

Run the MIGRATION_SQL string against your Supabase SQL Editor
or use the Supabase MCP tool to apply it.
"""

MIGRATION_SQL = """
-- ============================================================
-- ContentFlow API — Database Schema
-- Target: Supabase (PostgreSQL 15+)
-- ============================================================

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    plan        TEXT NOT NULL DEFAULT 'free'
                    CHECK (plan IN ('free', 'build', 'scale', 'enterprise')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. api_keys
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_prefix  TEXT NOT NULL,          -- 'cf_live_' or 'cf_test_'
    key_hash    TEXT NOT NULL,          -- bcrypt hash of the full key
    label       TEXT NOT NULL DEFAULT 'default',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);

-- 3. social_accounts
CREATE TABLE IF NOT EXISTS social_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform            TEXT NOT NULL,
    platform_account_id TEXT NOT NULL,
    display_name        TEXT,
    access_token_enc    TEXT,           -- AES-256 encrypted
    refresh_token_enc   TEXT,           -- AES-256 encrypted
    token_expires_at    TIMESTAMPTZ,
    scopes              TEXT[],
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, platform, platform_account_id)
);

-- 4. posts
CREATE TABLE IF NOT EXISTS posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text            TEXT,
    media_urls      TEXT[],
    media_type      TEXT CHECK (media_type IN ('video', 'image', 'carousel', 'text')),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'scheduled', 'publishing', 'published',
                                          'partially_failed', 'failed', 'cancelled')),
    scheduled_for   TIMESTAMPTZ,
    platform_options JSONB DEFAULT '{}'::jsonb,
    is_test         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_posts_user_status ON posts(user_id, status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON posts(scheduled_for) WHERE status = 'scheduled';

-- 5. post_platforms  (per-platform delivery status)
CREATE TABLE IF NOT EXISTS post_platforms (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    platform            TEXT NOT NULL,
    account_id          UUID REFERENCES social_accounts(id),
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'publishing', 'published', 'failed')),
    platform_post_id    TEXT,           -- ID on the target platform
    error_message       TEXT,
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_post_platforms_post ON post_platforms(post_id);

-- 6. video_jobs
CREATE TABLE IF NOT EXISTS video_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic           TEXT NOT NULL,
    mode            TEXT NOT NULL DEFAULT 'general',
    language        TEXT NOT NULL DEFAULT 'ko',
    format          TEXT NOT NULL DEFAULT 'shorts'
                        CHECK (format IN ('shorts', 'long', 'square')),
    style           TEXT NOT NULL DEFAULT 'realistic',
    status          TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'generating', 'completed', 'failed')),
    result_url      TEXT,
    auto_publish    JSONB,
    linked_post_id  UUID REFERENCES posts(id),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    events      TEXT[] NOT NULL DEFAULT '{}',
    secret      TEXT NOT NULL,           -- HMAC signing secret
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_social_accounts_updated_at
        BEFORE UPDATE ON social_accounts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_posts_updated_at
        BEFORE UPDATE ON posts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_video_jobs_updated_at
        BEFORE UPDATE ON video_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""
