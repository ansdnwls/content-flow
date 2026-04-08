from textwrap import dedent

CREATE_EXTENSIONS_SQL = dedent(
    """
    create extension if not exists pgcrypto;
    """
).strip()


CREATE_USERS_TABLE_SQL = dedent(
    """
    create table if not exists public.users (
        id uuid primary key default gen_random_uuid(),
        email text not null unique,
        full_name text,
        plan text not null default 'free',
        is_active boolean not null default true,
        stripe_customer_id text,
        stripe_subscription_id text,
        subscription_status text,
        current_period_end timestamptz,
        cancel_at_period_end boolean not null default false,
        email_verified boolean not null default false,
        email_verified_at timestamptz,
        onboarding_completed boolean not null default false,
        onboarding_steps jsonb not null default '{}'::jsonb,
        default_workspace_id uuid,
        language text not null default 'ko',
        timezone text not null default 'Asia/Seoul',
        data_processing_restricted boolean not null default false,
        deletion_scheduled_at timestamptz,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );
    """
).strip()


CREATE_WORKSPACES_TABLE_SQL = dedent(
    """
    create table if not exists public.workspaces (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        name text not null,
        slug text not null unique,
        branding jsonb not null default '{}'::jsonb,
        support_email text,
        custom_domain text unique,
        white_label_enabled boolean not null default false,
        domain_verification_token text,
        domain_verified_at timestamptz,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_workspaces_owner on public.workspaces(owner_id);
    """
).strip()


CREATE_WORKSPACE_MEMBERS_TABLE_SQL = dedent(
    """
    create table if not exists public.workspace_members (
        id uuid primary key default gen_random_uuid(),
        workspace_id uuid not null references public.workspaces(id) on delete cascade,
        user_id uuid not null references public.users(id) on delete cascade,
        role text not null default 'viewer',
        invited_by uuid references public.users(id) on delete set null,
        joined_at timestamptz not null default timezone('utc', now()),
        unique (workspace_id, user_id)
    );

    create index if not exists idx_workspace_members_user
        on public.workspace_members(user_id, workspace_id);
    """
).strip()


CREATE_API_KEYS_TABLE_SQL = dedent(
    """
    create table if not exists public.api_keys (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        workspace_id uuid references public.workspaces(id) on delete set null,
        name text not null,
        key_prefix text not null,
        key_preview text not null,
        hashed_key text not null,
        last_used_at timestamptz,
        expires_at timestamptz,
        rotated_from uuid references public.api_keys(id) on delete set null,
        is_active boolean not null default true,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create unique index if not exists idx_api_keys_user_workspace_name
        on public.api_keys(user_id, workspace_id, name);
    create index if not exists idx_api_keys_active on public.api_keys(user_id, is_active);
    """
).strip()


CREATE_SOCIAL_ACCOUNTS_TABLE_SQL = dedent(
    """
    create table if not exists public.social_accounts (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        workspace_id uuid references public.workspaces(id) on delete set null,
        platform text not null,
        handle text not null,
        display_name text,
        status text not null default 'active',
        encrypted_access_token text,
        encrypted_refresh_token text,
        token_expires_at timestamptz,
        metadata jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (owner_id, workspace_id, platform, handle)
    );

    create index if not exists idx_social_accounts_owner
        on public.social_accounts(owner_id, platform);
    create index if not exists idx_social_accounts_status
        on public.social_accounts(owner_id, status);
    """
).strip()


CREATE_POSTS_TABLE_SQL = dedent(
    """
    create table if not exists public.posts (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        workspace_id uuid references public.workspaces(id) on delete set null,
        api_key_id uuid references public.api_keys(id) on delete set null,
        text text,
        media_urls jsonb not null default '[]'::jsonb,
        media_type text not null default 'text',
        status text not null default 'pending',
        scheduled_for timestamptz,
        platform_options jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_posts_owner_status on public.posts(owner_id, status);
    create index if not exists idx_posts_scheduled_for
        on public.posts(scheduled_for)
        where scheduled_for is not null;
    """
).strip()


CREATE_POST_DELIVERIES_TABLE_SQL = dedent(
    """
    create table if not exists public.post_deliveries (
        id uuid primary key default gen_random_uuid(),
        post_id uuid not null references public.posts(id) on delete cascade,
        owner_id uuid not null references public.users(id) on delete cascade,
        social_account_id uuid references public.social_accounts(id) on delete set null,
        platform text not null,
        status text not null default 'pending',
        platform_post_id text,
        error_message text,
        published_at timestamptz,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (post_id, platform)
    );

    create index if not exists idx_post_deliveries_owner
        on public.post_deliveries(owner_id, platform, status);
    """
).strip()


CREATE_VIDEO_JOBS_TABLE_SQL = dedent(
    """
    create table if not exists public.video_jobs (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        workspace_id uuid references public.workspaces(id) on delete set null,
        api_key_id uuid references public.api_keys(id) on delete set null,
        topic text not null,
        mode text not null,
        language text not null default 'en',
        format text not null default 'shorts',
        style text,
        status text not null default 'queued',
        provider_job_id text,
        output_url text,
        auto_publish jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_video_jobs_owner_status on public.video_jobs(owner_id, status);
    """
).strip()


CREATE_WEBHOOKS_TABLE_SQL = dedent(
    """
    create table if not exists public.webhooks (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        target_url text not null,
        signing_secret text not null,
        event_types text[] not null default array['post.published'],
        is_active boolean not null default true,
        last_failure_at timestamptz,
        failure_count integer not null default 0,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_webhooks_owner_active on public.webhooks(owner_id, is_active);
    """
).strip()


CREATE_BOMBS_TABLE_SQL = dedent(
    """
    create table if not exists public.bombs (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        topic text not null,
        status text not null default 'queued',
        platform_contents jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_bombs_user_status on public.bombs(user_id, status);
    """
).strip()


CREATE_COMMENTS_TABLE_SQL = dedent(
    """
    create table if not exists public.comments (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        platform text not null,
        platform_post_id text not null,
        platform_comment_id text not null unique,
        author_id text not null default '',
        author_name text not null default '',
        text text not null,
        comment_created_at timestamptz,
        ai_reply text,
        reply_status text not null default 'pending',
        platform_reply_id text,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_comments_user_platform
        on public.comments(user_id, platform, reply_status);
    create unique index if not exists idx_comments_platform_comment_id
        on public.comments(platform_comment_id);
    """
).strip()


CREATE_SCHEDULES_TABLE_SQL = dedent(
    """
    create table if not exists public.schedules (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        post_id uuid references public.posts(id) on delete set null,
        platform text not null,
        tz text not null default 'UTC',
        recurrence text not null default 'once',
        cron_expression text,
        next_run_at timestamptz not null,
        is_active boolean not null default true,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_schedules_user_active
        on public.schedules(user_id, is_active);
    create index if not exists idx_schedules_next_run
        on public.schedules(next_run_at)
        where is_active = true;
    """
).strip()


CREATE_ANALYTICS_SNAPSHOTS_TABLE_SQL = dedent(
    """
    create table if not exists public.analytics_snapshots (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        platform text not null,
        platform_post_id text,
        snapshot_date date not null default current_date,
        views integer not null default 0,
        likes integer not null default 0,
        comments integer not null default 0,
        shares integer not null default 0,
        followers integer not null default 0,
        impressions integer not null default 0,
        reach integer not null default 0,
        engagement_rate numeric(6,2) not null default 0,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (owner_id, platform, platform_post_id, snapshot_date)
    );

    create index if not exists idx_analytics_snapshots_owner_date
        on public.analytics_snapshots(owner_id, snapshot_date);
    create index if not exists idx_analytics_snapshots_platform
        on public.analytics_snapshots(owner_id, platform, snapshot_date);
    """
).strip()


CREATE_WEBHOOK_DELIVERIES_TABLE_SQL = dedent(
    """
    create table if not exists public.webhook_deliveries (
        id uuid primary key default gen_random_uuid(),
        webhook_id uuid not null references public.webhooks(id) on delete cascade,
        owner_id uuid not null references public.users(id) on delete cascade,
        event text not null,
        idempotency_key text not null,
        payload jsonb not null default '{}'::jsonb,
        status text not null default 'pending',
        attempts integer not null default 0,
        max_attempts integer not null default 6,
        last_error text,
        next_retry_at timestamptz,
        delivered_at timestamptz,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_webhook_deliveries_webhook
        on public.webhook_deliveries(webhook_id, status);
    create unique index if not exists idx_webhook_deliveries_idempotency_key
        on public.webhook_deliveries(idempotency_key);
    create index if not exists idx_webhook_deliveries_retry
        on public.webhook_deliveries(status, next_retry_at)
        where status = 'pending';
    create index if not exists idx_webhook_deliveries_owner
        on public.webhook_deliveries(owner_id, status);
    """
).strip()


CREATE_VIDEO_TEMPLATES_TABLE_SQL = dedent(
    """
    create table if not exists public.video_templates (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        name text not null,
        description text not null default '',
        duration_seconds int not null default 60,
        scenes jsonb not null default '[]'::jsonb,
        caption_style text not null default 'bold_white',
        voice_tone text not null default 'neutral',
        bgm_mood text not null default 'ambient',
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_video_templates_owner
        on public.video_templates(owner_id);
    """
).strip()


CREATE_TRENDING_SNAPSHOTS_TABLE_SQL = dedent(
    """
    create table if not exists public.trending_snapshots (
        id uuid primary key default gen_random_uuid(),
        owner_id uuid not null references public.users(id) on delete cascade,
        platform text not null,
        region text not null default 'US',
        items jsonb not null default '[]'::jsonb,
        fetched_at timestamptz not null default timezone('utc', now()),
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_trending_snapshots_owner_platform
        on public.trending_snapshots(owner_id, platform, region);
    """
).strip()


CREATE_EMAIL_LOGS_TABLE_SQL = dedent(
    """
    create table if not exists public.email_logs (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        to_email text not null,
        subject text not null,
        template text,
        status text not null default 'pending',
        error text,
        sent_at timestamptz,
        created_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_email_logs_user
        on public.email_logs(user_id, created_at desc);
    """
).strip()


CREATE_NOTIFICATION_PREFERENCES_TABLE_SQL = dedent(
    """
    create table if not exists public.notification_preferences (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        product_updates boolean not null default true,
        billing boolean not null default true,
        security boolean not null default true,
        monthly_summary boolean not null default true,
        webhook_alerts boolean not null default true,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (user_id)
    );
    """
).strip()


CREATE_PAYMENTS_TABLE_SQL = dedent(
    """
    create table if not exists public.payments (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        stripe_invoice_id text,
        amount integer not null,
        currency text not null default 'usd',
        status text not null default 'pending',
        paid_at timestamptz,
        created_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_payments_user
        on public.payments(user_id, created_at desc);
    """
).strip()


CREATE_SUBSCRIPTION_EVENTS_TABLE_SQL = dedent(
    """
    create table if not exists public.subscription_events (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        event_type text not null,
        from_plan text,
        to_plan text,
        metadata jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_subscription_events_user
        on public.subscription_events(user_id, created_at desc);
    """
).strip()


CREATE_AUDIT_LOGS_TABLE_SQL = dedent(
    """
    create table if not exists public.audit_logs (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        api_key_id uuid references public.api_keys(id) on delete set null,
        action text not null,
        resource text not null,
        ip inet,
        user_agent text,
        metadata jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_audit_logs_user
        on public.audit_logs(user_id, created_at desc);
    create index if not exists idx_audit_logs_action
        on public.audit_logs(user_id, action);
    create index if not exists idx_audit_logs_resource
        on public.audit_logs(user_id, resource);
    """
).strip()


CREATE_CONSENTS_TABLE_SQL = dedent(
    """
    create table if not exists public.consents (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        purpose text not null,
        granted boolean not null default false,
        granted_at timestamptz,
        revoked_at timestamptz,
        ip inet,
        user_agent text,
        version text not null default '1.0',
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (user_id, purpose)
    );

    create index if not exists idx_consents_user
        on public.consents(user_id);
    """
).strip()


CREATE_DPA_SIGNATURES_TABLE_SQL = dedent(
    """
    create table if not exists public.dpa_signatures (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        dpa_version text not null,
        signer_name text not null,
        signer_email text not null,
        company text not null,
        signed_at timestamptz not null default timezone('utc', now()),
        ip inet,
        pdf_url text,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_dpa_signatures_user
        on public.dpa_signatures(user_id);
    """
).strip()


CREATE_DATA_BREACHES_TABLE_SQL = dedent(
    """
    create table if not exists public.data_breaches (
        id uuid primary key default gen_random_uuid(),
        reported_by uuid references public.users(id) on delete set null,
        severity text not null default 'medium',
        affected_user_count integer not null default 0,
        description text not null,
        status text not null default 'reported',
        notified_users_at timestamptz,
        notified_authority_at timestamptz,
        resolved_at timestamptz,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now())
    );
    """
).strip()


CREATE_DELETION_REQUESTS_TABLE_SQL = dedent(
    """
    create table if not exists public.deletion_requests (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        status text not null default 'pending',
        reason text,
        requested_at timestamptz not null default timezone('utc', now()),
        scheduled_for timestamptz not null,
        completed_at timestamptz,
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (user_id)
    );

    create index if not exists idx_deletion_requests_status
        on public.deletion_requests(status, scheduled_for);
    """
).strip()


CREATE_YTBOOST_SUBSCRIPTIONS_TABLE_SQL = dedent(
    """
    create table if not exists public.ytboost_subscriptions (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        youtube_channel_id text not null,
        channel_name text,
        subscribed_at timestamptz not null default timezone('utc', now()),
        last_checked_at timestamptz,
        auto_distribute boolean not null default false,
        target_platforms jsonb not null default '[]'::jsonb,
        auto_comment_mode text not null default 'review',
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (user_id, youtube_channel_id)
    );

    create index if not exists idx_ytboost_subscriptions_user
        on public.ytboost_subscriptions(user_id, youtube_channel_id);
    """
).strip()


CREATE_YTBOOST_SHORTS_TABLE_SQL = dedent(
    """
    create table if not exists public.ytboost_shorts (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        source_video_id text not null,
        source_channel_id text not null,
        start_seconds integer not null default 0,
        end_seconds integer not null default 60,
        hook_line text,
        suggested_title text,
        suggested_hashtags jsonb not null default '[]'::jsonb,
        reason text,
        clip_file_url text,
        status text not null default 'pending',
        created_at timestamptz not null default timezone('utc', now()),
        approved_at timestamptz,
        updated_at timestamptz not null default timezone('utc', now())
    );

    create index if not exists idx_ytboost_shorts_user
        on public.ytboost_shorts(user_id, status, created_at desc);
    create index if not exists idx_ytboost_shorts_source
        on public.ytboost_shorts(source_video_id, source_channel_id);
    """
).strip()


CREATE_YTBOOST_CHANNEL_TONES_TABLE_SQL = dedent(
    """
    create table if not exists public.ytboost_channel_tones (
        id uuid primary key default gen_random_uuid(),
        user_id uuid not null references public.users(id) on delete cascade,
        youtube_channel_id text not null,
        tone_profile jsonb not null default '{}'::jsonb,
        sample_size integer not null default 0,
        learned_at timestamptz not null default timezone('utc', now()),
        created_at timestamptz not null default timezone('utc', now()),
        updated_at timestamptz not null default timezone('utc', now()),
        unique (user_id, youtube_channel_id)
    );

    create index if not exists idx_ytboost_channel_tones_user
        on public.ytboost_channel_tones(user_id, youtube_channel_id);
    """
).strip()


CREATE_UPDATED_AT_FUNCTION_SQL = dedent(
    """
    create or replace function public.set_updated_at()
    returns trigger
    language plpgsql
    as $$
    begin
        new.updated_at = timezone('utc', now());
        return new;
    end;
    $$;
    """
).strip()


CREATE_UPDATED_AT_TRIGGERS_SQL = dedent(
    """
    drop trigger if exists trg_users_updated_at on public.users;
    create trigger trg_users_updated_at before update on public.users
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_api_keys_updated_at on public.api_keys;
    create trigger trg_api_keys_updated_at before update on public.api_keys
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_workspaces_updated_at on public.workspaces;
    create trigger trg_workspaces_updated_at before update on public.workspaces
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_social_accounts_updated_at on public.social_accounts;
    create trigger trg_social_accounts_updated_at before update on public.social_accounts
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_posts_updated_at on public.posts;
    create trigger trg_posts_updated_at before update on public.posts
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_post_deliveries_updated_at on public.post_deliveries;
    create trigger trg_post_deliveries_updated_at before update on public.post_deliveries
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_video_jobs_updated_at on public.video_jobs;
    create trigger trg_video_jobs_updated_at before update on public.video_jobs
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_webhooks_updated_at on public.webhooks;
    create trigger trg_webhooks_updated_at before update on public.webhooks
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_bombs_updated_at on public.bombs;
    create trigger trg_bombs_updated_at before update on public.bombs
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_comments_updated_at on public.comments;
    create trigger trg_comments_updated_at before update on public.comments
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_schedules_updated_at on public.schedules;
    create trigger trg_schedules_updated_at before update on public.schedules
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_analytics_snapshots_updated_at on public.analytics_snapshots;
    create trigger trg_analytics_snapshots_updated_at before update on public.analytics_snapshots
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_webhook_deliveries_updated_at on public.webhook_deliveries;
    create trigger trg_webhook_deliveries_updated_at before update on public.webhook_deliveries
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_video_templates_updated_at on public.video_templates;
    create trigger trg_video_templates_updated_at before update on public.video_templates
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_trending_snapshots_updated_at on public.trending_snapshots;
    create trigger trg_trending_snapshots_updated_at before update on public.trending_snapshots
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_consents_updated_at on public.consents;
    create trigger trg_consents_updated_at before update on public.consents
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_dpa_signatures_updated_at on public.dpa_signatures;
    create trigger trg_dpa_signatures_updated_at before update on public.dpa_signatures
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_data_breaches_updated_at on public.data_breaches;
    create trigger trg_data_breaches_updated_at before update on public.data_breaches
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_deletion_requests_updated_at on public.deletion_requests;
    create trigger trg_deletion_requests_updated_at before update on public.deletion_requests
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_ytboost_subscriptions_updated_at on public.ytboost_subscriptions;
    create trigger trg_ytboost_subscriptions_updated_at
    before update on public.ytboost_subscriptions
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_ytboost_shorts_updated_at on public.ytboost_shorts;
    create trigger trg_ytboost_shorts_updated_at before update on public.ytboost_shorts
    for each row execute function public.set_updated_at();

    drop trigger if exists trg_ytboost_channel_tones_updated_at on public.ytboost_channel_tones;
    create trigger trg_ytboost_channel_tones_updated_at
    before update on public.ytboost_channel_tones
    for each row execute function public.set_updated_at();
    """
).strip()


SCHEMA_SQL_STATEMENTS = [
    CREATE_EXTENSIONS_SQL,
    CREATE_USERS_TABLE_SQL,
    CREATE_WORKSPACES_TABLE_SQL,
    CREATE_WORKSPACE_MEMBERS_TABLE_SQL,
    CREATE_API_KEYS_TABLE_SQL,
    CREATE_SOCIAL_ACCOUNTS_TABLE_SQL,
    CREATE_POSTS_TABLE_SQL,
    CREATE_POST_DELIVERIES_TABLE_SQL,
    CREATE_VIDEO_JOBS_TABLE_SQL,
    CREATE_WEBHOOKS_TABLE_SQL,
    CREATE_BOMBS_TABLE_SQL,
    CREATE_COMMENTS_TABLE_SQL,
    CREATE_SCHEDULES_TABLE_SQL,
    CREATE_ANALYTICS_SNAPSHOTS_TABLE_SQL,
    CREATE_WEBHOOK_DELIVERIES_TABLE_SQL,
    CREATE_VIDEO_TEMPLATES_TABLE_SQL,
    CREATE_TRENDING_SNAPSHOTS_TABLE_SQL,
    CREATE_EMAIL_LOGS_TABLE_SQL,
    CREATE_NOTIFICATION_PREFERENCES_TABLE_SQL,
    CREATE_PAYMENTS_TABLE_SQL,
    CREATE_SUBSCRIPTION_EVENTS_TABLE_SQL,
    CREATE_AUDIT_LOGS_TABLE_SQL,
    CREATE_CONSENTS_TABLE_SQL,
    CREATE_DPA_SIGNATURES_TABLE_SQL,
    CREATE_DATA_BREACHES_TABLE_SQL,
    CREATE_DELETION_REQUESTS_TABLE_SQL,
    CREATE_YTBOOST_SUBSCRIPTIONS_TABLE_SQL,
    CREATE_YTBOOST_SHORTS_TABLE_SQL,
    CREATE_YTBOOST_CHANNEL_TONES_TABLE_SQL,
    CREATE_UPDATED_AT_FUNCTION_SQL,
    CREATE_UPDATED_AT_TRIGGERS_SQL,
]

SCHEMA_SQL = "\n\n".join(SCHEMA_SQL_STATEMENTS)
