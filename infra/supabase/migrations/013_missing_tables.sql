-- Backfill missing table definitions that were present only in the Python fake DB.
-- Also patches core tables with columns introduced by the application layer.
-- Duplicate ytboost tables are intentionally excluded because 011_ytboost.sql owns them.

-- ---------------------------------------------------------------------------
-- Patch existing core tables to match application queries
-- ---------------------------------------------------------------------------

alter table public.api_keys
    add column if not exists workspace_id uuid,
    add column if not exists rotated_from uuid;

alter table public.social_accounts
    add column if not exists workspace_id uuid,
    add column if not exists status text not null default 'active';

alter table public.posts
    add column if not exists workspace_id uuid;

alter table public.video_jobs
    add column if not exists workspace_id uuid,
    add column if not exists template text;

create index if not exists idx_api_keys_workspace_id
    on public.api_keys(workspace_id);

create index if not exists idx_social_accounts_workspace_id
    on public.social_accounts(workspace_id);

create index if not exists idx_posts_workspace_id
    on public.posts(workspace_id, created_at desc);

create index if not exists idx_video_jobs_workspace_id
    on public.video_jobs(workspace_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Missing tables
-- ---------------------------------------------------------------------------

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

create table if not exists public.workspace_members (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references public.workspaces(id) on delete cascade,
    user_id uuid not null references public.users(id) on delete cascade,
    role text not null default 'viewer',
    invited_by uuid references public.users(id) on delete set null,
    joined_at timestamptz not null default timezone('utc', now()),
    unique (workspace_id, user_id)
);

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

create table if not exists public.bombs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    topic text not null,
    status text not null default 'queued',
    platform_contents jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

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

create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    type text not null,
    title text not null,
    body text not null,
    link_url text,
    read_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.onboarding_progress (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    step text not null,
    completed_at timestamptz,
    data jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (user_id, step)
);

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

create table if not exists public.shopsync_bulk_jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    status text not null default 'pending',
    total_rows integer not null default 0,
    succeeded integer not null default 0,
    failed integer not null default 0,
    results jsonb not null default '[]'::jsonb,
    error text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.shopsync_products (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    product_name text not null,
    price integer not null,
    category text not null default '',
    image_urls jsonb not null default '[]'::jsonb,
    target_platforms jsonb not null default '[]'::jsonb,
    channels_generated jsonb not null default '[]'::jsonb,
    status text not null default 'generated',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.subscription_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    event_type text not null,
    from_plan text,
    to_plan text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

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

create table if not exists public.video_templates (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.users(id) on delete cascade,
    name text not null,
    description text not null default '',
    duration_seconds integer not null default 60,
    scenes jsonb not null default '[]'::jsonb,
    caption_style text not null default 'bold_white',
    voice_tone text not null default 'neutral',
    bgm_mood text not null default 'ambient',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

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

-- ---------------------------------------------------------------------------
-- Foreign keys that depend on newly created tables
-- ---------------------------------------------------------------------------

alter table public.users
    add column if not exists default_workspace_id uuid;

do $$
begin
    if not exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'users'
          and constraint_name = 'users_default_workspace_id_fkey'
    ) then
        alter table public.users
            add constraint users_default_workspace_id_fkey
            foreign key (default_workspace_id)
            references public.workspaces(id)
            on delete set null;
    end if;
end $$;

do $$
begin
    if not exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'api_keys'
          and constraint_name = 'api_keys_workspace_id_fkey'
    ) then
        alter table public.api_keys
            add constraint api_keys_workspace_id_fkey
            foreign key (workspace_id)
            references public.workspaces(id)
            on delete set null;
    end if;
end $$;

do $$
begin
    if not exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'api_keys'
          and constraint_name = 'api_keys_rotated_from_fkey'
    ) then
        alter table public.api_keys
            add constraint api_keys_rotated_from_fkey
            foreign key (rotated_from)
            references public.api_keys(id)
            on delete set null;
    end if;
end $$;

do $$
begin
    if not exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'social_accounts'
          and constraint_name = 'social_accounts_workspace_id_fkey'
    ) then
        alter table public.social_accounts
            add constraint social_accounts_workspace_id_fkey
            foreign key (workspace_id)
            references public.workspaces(id)
            on delete set null;
    end if;
end $$;

do $$
begin
    if not exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'posts'
          and constraint_name = 'posts_workspace_id_fkey'
    ) then
        alter table public.posts
            add constraint posts_workspace_id_fkey
            foreign key (workspace_id)
            references public.workspaces(id)
            on delete set null;
    end if;
end $$;

do $$
begin
    if not exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'video_jobs'
          and constraint_name = 'video_jobs_workspace_id_fkey'
    ) then
        alter table public.video_jobs
            add constraint video_jobs_workspace_id_fkey
            foreign key (workspace_id)
            references public.workspaces(id)
            on delete set null;
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

create index if not exists idx_workspaces_owner
    on public.workspaces(owner_id);

create index if not exists idx_workspaces_slug
    on public.workspaces(slug);

create index if not exists idx_workspace_members_user
    on public.workspace_members(user_id, workspace_id);

create index if not exists idx_analytics_snapshots_owner_date
    on public.analytics_snapshots(owner_id, snapshot_date desc);

create index if not exists idx_analytics_snapshots_platform
    on public.analytics_snapshots(owner_id, platform, snapshot_date desc);

create index if not exists idx_audit_logs_user
    on public.audit_logs(user_id, created_at desc);

create index if not exists idx_audit_logs_action
    on public.audit_logs(action, created_at desc);

create index if not exists idx_audit_logs_resource
    on public.audit_logs(resource, created_at desc);

create index if not exists idx_bombs_user_status
    on public.bombs(user_id, status, created_at desc);

create index if not exists idx_comments_user_platform
    on public.comments(user_id, platform, reply_status, created_at desc);

create index if not exists idx_comments_platform_post
    on public.comments(platform, platform_post_id);

create index if not exists idx_consents_user
    on public.consents(user_id);

create index if not exists idx_data_breaches_status
    on public.data_breaches(status, created_at desc);

create index if not exists idx_deletion_requests_status
    on public.deletion_requests(status, scheduled_for);

create index if not exists idx_dpa_signatures_user
    on public.dpa_signatures(user_id, signed_at desc);

create index if not exists idx_email_logs_user
    on public.email_logs(user_id, created_at desc);

create index if not exists idx_notifications_user_unread
    on public.notifications(user_id, created_at desc)
    where read_at is null;

create index if not exists idx_notifications_user
    on public.notifications(user_id, created_at desc);

create index if not exists idx_onboarding_progress_user
    on public.onboarding_progress(user_id, step);

create index if not exists idx_payments_user
    on public.payments(user_id, created_at desc);

create index if not exists idx_schedules_user_active
    on public.schedules(user_id, is_active);

create index if not exists idx_schedules_next_run
    on public.schedules(next_run_at)
    where is_active = true;

create index if not exists idx_shopsync_bulk_jobs_user
    on public.shopsync_bulk_jobs(user_id, created_at desc);

create index if not exists idx_shopsync_bulk_jobs_status
    on public.shopsync_bulk_jobs(status, created_at desc);

create index if not exists idx_shopsync_products_user
    on public.shopsync_products(user_id, created_at desc);

create index if not exists idx_shopsync_products_status
    on public.shopsync_products(user_id, status, created_at desc);

create index if not exists idx_subscription_events_user
    on public.subscription_events(user_id, created_at desc);

create index if not exists idx_trending_snapshots_owner_platform
    on public.trending_snapshots(owner_id, platform, region, fetched_at desc);

create index if not exists idx_video_templates_owner
    on public.video_templates(owner_id, created_at desc);

create unique index if not exists idx_webhook_deliveries_idempotency_key
    on public.webhook_deliveries(idempotency_key);

create index if not exists idx_webhook_deliveries_webhook
    on public.webhook_deliveries(webhook_id, status, created_at desc);

create index if not exists idx_webhook_deliveries_retry
    on public.webhook_deliveries(status, next_retry_at)
    where status in ('pending', 'failed');

create index if not exists idx_webhook_deliveries_owner
    on public.webhook_deliveries(owner_id, created_at desc);

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------

drop trigger if exists trg_workspaces_updated_at on public.workspaces;
create trigger trg_workspaces_updated_at
before update on public.workspaces
for each row execute function public.set_updated_at();

drop trigger if exists trg_analytics_snapshots_updated_at on public.analytics_snapshots;
create trigger trg_analytics_snapshots_updated_at
before update on public.analytics_snapshots
for each row execute function public.set_updated_at();

drop trigger if exists trg_bombs_updated_at on public.bombs;
create trigger trg_bombs_updated_at
before update on public.bombs
for each row execute function public.set_updated_at();

drop trigger if exists trg_comments_updated_at on public.comments;
create trigger trg_comments_updated_at
before update on public.comments
for each row execute function public.set_updated_at();

drop trigger if exists trg_consents_updated_at on public.consents;
create trigger trg_consents_updated_at
before update on public.consents
for each row execute function public.set_updated_at();

drop trigger if exists trg_data_breaches_updated_at on public.data_breaches;
create trigger trg_data_breaches_updated_at
before update on public.data_breaches
for each row execute function public.set_updated_at();

drop trigger if exists trg_deletion_requests_updated_at on public.deletion_requests;
create trigger trg_deletion_requests_updated_at
before update on public.deletion_requests
for each row execute function public.set_updated_at();

drop trigger if exists trg_dpa_signatures_updated_at on public.dpa_signatures;
create trigger trg_dpa_signatures_updated_at
before update on public.dpa_signatures
for each row execute function public.set_updated_at();

drop trigger if exists trg_notification_preferences_updated_at on public.notification_preferences;
create trigger trg_notification_preferences_updated_at
before update on public.notification_preferences
for each row execute function public.set_updated_at();

drop trigger if exists trg_notifications_updated_at on public.notifications;
create trigger trg_notifications_updated_at
before update on public.notifications
for each row execute function public.set_updated_at();

drop trigger if exists trg_onboarding_progress_updated_at on public.onboarding_progress;
create trigger trg_onboarding_progress_updated_at
before update on public.onboarding_progress
for each row execute function public.set_updated_at();

drop trigger if exists trg_schedules_updated_at on public.schedules;
create trigger trg_schedules_updated_at
before update on public.schedules
for each row execute function public.set_updated_at();

drop trigger if exists trg_shopsync_bulk_jobs_updated_at on public.shopsync_bulk_jobs;
create trigger trg_shopsync_bulk_jobs_updated_at
before update on public.shopsync_bulk_jobs
for each row execute function public.set_updated_at();

drop trigger if exists trg_shopsync_products_updated_at on public.shopsync_products;
create trigger trg_shopsync_products_updated_at
before update on public.shopsync_products
for each row execute function public.set_updated_at();

drop trigger if exists trg_trending_snapshots_updated_at on public.trending_snapshots;
create trigger trg_trending_snapshots_updated_at
before update on public.trending_snapshots
for each row execute function public.set_updated_at();

drop trigger if exists trg_video_templates_updated_at on public.video_templates;
create trigger trg_video_templates_updated_at
before update on public.video_templates
for each row execute function public.set_updated_at();

drop trigger if exists trg_webhook_deliveries_updated_at on public.webhook_deliveries;
create trigger trg_webhook_deliveries_updated_at
before update on public.webhook_deliveries
for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.analytics_snapshots enable row level security;
alter table public.audit_logs enable row level security;
alter table public.bombs enable row level security;
alter table public.comments enable row level security;
alter table public.consents enable row level security;
alter table public.data_breaches enable row level security;
alter table public.deletion_requests enable row level security;
alter table public.dpa_signatures enable row level security;
alter table public.email_logs enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.notifications enable row level security;
alter table public.onboarding_progress enable row level security;
alter table public.payments enable row level security;
alter table public.schedules enable row level security;
alter table public.shopsync_bulk_jobs enable row level security;
alter table public.shopsync_products enable row level security;
alter table public.subscription_events enable row level security;
alter table public.trending_snapshots enable row level security;
alter table public.video_templates enable row level security;
alter table public.webhook_deliveries enable row level security;

drop policy if exists "workspaces_member_select" on public.workspaces;
create policy "workspaces_member_select"
on public.workspaces
for select
to authenticated
using (
    owner_id = auth.uid()
    or exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = public.workspaces.id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspaces_owner_manage" on public.workspaces;
create policy "workspaces_owner_manage"
on public.workspaces
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

drop policy if exists "workspace_members_access" on public.workspace_members;
create policy "workspace_members_access"
on public.workspace_members
for all
to authenticated
using (
    user_id = auth.uid()
    or exists (
        select 1
        from public.workspaces w
        where w.id = public.workspace_members.workspace_id
          and w.owner_id = auth.uid()
    )
)
with check (
    exists (
        select 1
        from public.workspaces w
        where w.id = public.workspace_members.workspace_id
          and w.owner_id = auth.uid()
    )
);

drop policy if exists "analytics_snapshots_owner_access" on public.analytics_snapshots;
create policy "analytics_snapshots_owner_access"
on public.analytics_snapshots
for select
to authenticated
using (owner_id = auth.uid());

drop policy if exists "audit_logs_owner_access" on public.audit_logs;
create policy "audit_logs_owner_access"
on public.audit_logs
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists "bombs_owner_access" on public.bombs;
create policy "bombs_owner_access"
on public.bombs
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "comments_owner_access" on public.comments;
create policy "comments_owner_access"
on public.comments
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "consents_owner_access" on public.consents;
create policy "consents_owner_access"
on public.consents
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "data_breaches_service_role_only" on public.data_breaches;
create policy "data_breaches_service_role_only"
on public.data_breaches
for all
to authenticated
using (false)
with check (false);

drop policy if exists "deletion_requests_owner_access" on public.deletion_requests;
create policy "deletion_requests_owner_access"
on public.deletion_requests
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "dpa_signatures_owner_access" on public.dpa_signatures;
create policy "dpa_signatures_owner_access"
on public.dpa_signatures
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "email_logs_owner_access" on public.email_logs;
create policy "email_logs_owner_access"
on public.email_logs
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists "notification_preferences_owner_access" on public.notification_preferences;
create policy "notification_preferences_owner_access"
on public.notification_preferences
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "notifications_owner_access" on public.notifications;
create policy "notifications_owner_access"
on public.notifications
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "onboarding_progress_owner_access" on public.onboarding_progress;
create policy "onboarding_progress_owner_access"
on public.onboarding_progress
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "payments_owner_access" on public.payments;
create policy "payments_owner_access"
on public.payments
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists "schedules_owner_access" on public.schedules;
create policy "schedules_owner_access"
on public.schedules
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "shopsync_bulk_jobs_owner_access" on public.shopsync_bulk_jobs;
create policy "shopsync_bulk_jobs_owner_access"
on public.shopsync_bulk_jobs
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "shopsync_products_owner_access" on public.shopsync_products;
create policy "shopsync_products_owner_access"
on public.shopsync_products
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "subscription_events_owner_access" on public.subscription_events;
create policy "subscription_events_owner_access"
on public.subscription_events
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists "trending_snapshots_owner_access" on public.trending_snapshots;
create policy "trending_snapshots_owner_access"
on public.trending_snapshots
for select
to authenticated
using (owner_id = auth.uid());

drop policy if exists "video_templates_owner_access" on public.video_templates;
create policy "video_templates_owner_access"
on public.video_templates
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

drop policy if exists "webhook_deliveries_owner_access" on public.webhook_deliveries;
create policy "webhook_deliveries_owner_access"
on public.webhook_deliveries
for select
to authenticated
using (owner_id = auth.uid());
