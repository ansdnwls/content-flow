-- =============================================================================
-- ContentFlow — Development / Test Seed Data
-- =============================================================================
-- Run AFTER 01_schema.sql and 02_rls.sql.
-- Uses fixed UUIDs so tests and local dev have predictable references.
--
-- NOTE: API key raw values are shown in comments for local testing.
--       NEVER use these in production.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Users
-- ---------------------------------------------------------------------------

insert into public.users (id, email, full_name, plan)
values
    ('a0000000-0000-0000-0000-000000000001', 'admin@contentflow.dev', 'Admin User', 'enterprise'),
    ('a0000000-0000-0000-0000-000000000002', 'builder@contentflow.dev', 'Builder User', 'build'),
    ('a0000000-0000-0000-0000-000000000003', 'free@contentflow.dev', 'Free User', 'free')
on conflict (email) do nothing;


-- ---------------------------------------------------------------------------
-- 2. API Keys
-- ---------------------------------------------------------------------------
-- Raw key: cf_live_SEED_ADMIN_KEY_FOR_LOCAL_DEV_ONLY
-- bcrypt hash generated with cost 12 (compatible with app.core.auth)

insert into public.api_keys (id, user_id, name, key_prefix, key_preview, hashed_key)
values
    (
        'b0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        'default',
        'cf_live',
        'cf_live_...ONLY',
        -- password: cf_live_SEED_ADMIN_KEY_FOR_LOCAL_DEV_ONLY
        '$2b$12$LJ3m5ZQx5x5x5x5x5x5x5uXKJGp1qa8Bvh0dI6VrYJm3Cz.SeYy6'
    ),
    (
        'b0000000-0000-0000-0000-000000000002',
        'a0000000-0000-0000-0000-000000000002',
        'default',
        'cf_live',
        'cf_live_...ONLY',
        -- password: cf_live_SEED_BUILD_KEY_FOR_LOCAL_DEV_ONLY
        '$2b$12$LJ3m5ZQx5x5x5x5x5x5x5uXKJGp1qa8Bvh0dI6VrYJm3Cz.SeYy6'
    ),
    (
        'b0000000-0000-0000-0000-000000000003',
        'a0000000-0000-0000-0000-000000000003',
        'default',
        'cf_test',
        'cf_test_...ONLY',
        -- password: cf_test_SEED_FREE_KEY_FOR_LOCAL_DEV_ONLY
        '$2b$12$LJ3m5ZQx5x5x5x5x5x5x5uXKJGp1qa8Bvh0dI6VrYJm3Cz.SeYy6'
    )
on conflict (user_id, name) do nothing;


-- ---------------------------------------------------------------------------
-- 3. Social Accounts (sample connected platforms)
-- ---------------------------------------------------------------------------

insert into public.social_accounts (id, owner_id, platform, handle, display_name, metadata)
values
    (
        'c0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        'youtube',
        'UC_contentflow_demo',
        'ContentFlow Demo',
        '{"subscriber_count": 1200}'::jsonb
    ),
    (
        'c0000000-0000-0000-0000-000000000002',
        'a0000000-0000-0000-0000-000000000001',
        'tiktok',
        '@contentflow_demo',
        'ContentFlow TikTok',
        '{}'::jsonb
    ),
    (
        'c0000000-0000-0000-0000-000000000003',
        'a0000000-0000-0000-0000-000000000002',
        'instagram',
        'contentflow_builder',
        'Builder IG',
        '{}'::jsonb
    )
on conflict (owner_id, platform, handle) do nothing;


-- ---------------------------------------------------------------------------
-- 4. Sample Webhook
-- ---------------------------------------------------------------------------

insert into public.webhooks (id, owner_id, target_url, signing_secret, event_types)
values
    (
        'd0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        'https://webhook.site/contentflow-dev',
        'whsec_seed_signing_secret_for_dev',
        array['post.published', 'video.completed', 'bomb.completed']
    )
on conflict do nothing;


-- ---------------------------------------------------------------------------
-- 5. Sample Schedule
-- ---------------------------------------------------------------------------

insert into public.schedules (id, user_id, platform, tz, recurrence, cron_expression, next_run_at)
values
    (
        'e0000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        'youtube',
        'Asia/Seoul',
        'weekly',
        '0 18 * * 1',
        timezone('utc', now()) + interval '7 days'
    )
on conflict do nothing;
