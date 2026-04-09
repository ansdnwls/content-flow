-- Performance indexes for high-traffic read and queue paths.
-- Uses guarded DDL so it remains compatible with both owner_id- and user_id-based schemas.

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'posts' and column_name = 'user_id'
    ) then
        execute 'create index if not exists idx_posts_user_status_created_desc
                 on public.posts(user_id, status, created_at desc)';
    elsif exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'posts' and column_name = 'owner_id'
    ) then
        execute 'create index if not exists idx_posts_owner_status_created_desc
                 on public.posts(owner_id, status, created_at desc)';
    end if;
end $$;

create index if not exists idx_posts_scheduled_only
    on public.posts(scheduled_for)
    where status = 'scheduled';

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'video_jobs' and column_name = 'user_id'
    ) then
        execute 'create index if not exists idx_video_jobs_user_status_created_desc
                 on public.video_jobs(user_id, status, created_at desc)';
    elsif exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'video_jobs' and column_name = 'owner_id'
    ) then
        execute 'create index if not exists idx_video_jobs_owner_status_created_desc
                 on public.video_jobs(owner_id, status, created_at desc)';
    end if;
end $$;

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'analytics_snapshots' and column_name = 'user_id'
    ) then
        execute 'create index if not exists idx_analytics_snapshots_user_date_desc
                 on public.analytics_snapshots(user_id, snapshot_date desc)';
    elsif exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'analytics_snapshots' and column_name = 'owner_id'
    ) then
        execute 'create index if not exists idx_analytics_snapshots_owner_date_desc
                 on public.analytics_snapshots(owner_id, snapshot_date desc)';
    end if;
end $$;

do $$
begin
    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'audit_logs'
    ) then
        execute 'create index if not exists idx_audit_logs_user_created_desc
                 on public.audit_logs(user_id, created_at desc)';
    end if;
end $$;

do $$
begin
    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'audit_logs'
    ) then
        execute 'create index if not exists idx_audit_logs_action_created_desc
                 on public.audit_logs(action, created_at desc)';
    end if;
end $$;

do $$
begin
    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'webhook_deliveries'
    ) then
        execute 'create index if not exists idx_webhook_deliveries_pending_failed_retry
                 on public.webhook_deliveries(status, next_retry_at)
                 where status in (''pending'', ''failed'')';
    end if;
end $$;

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'social_accounts' and column_name = 'user_id'
    ) then
        execute 'create index if not exists idx_social_accounts_user_platform
                 on public.social_accounts(user_id, platform)';
    elsif exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'social_accounts' and column_name = 'owner_id'
    ) then
        execute 'create index if not exists idx_social_accounts_owner_platform_perf
                 on public.social_accounts(owner_id, platform)';
    end if;
end $$;

do $$
begin
    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'usage'
    ) and exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'usage' and column_name = 'user_id'
    ) and exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'usage' and column_name = 'year_month'
    ) then
        execute 'create index if not exists idx_usage_user_year_month
                 on public.usage(user_id, year_month)';
    end if;
end $$;
