create extension if not exists pgcrypto;

create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    full_name text,
    plan text not null default 'free',
    is_active boolean not null default true,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.api_keys (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    name text not null,
    key_prefix text not null,
    key_preview text not null,
    hashed_key text not null,
    last_used_at timestamptz,
    expires_at timestamptz,
    is_active boolean not null default true,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists idx_api_keys_user_name on public.api_keys(user_id, name);
create index if not exists idx_api_keys_active on public.api_keys(user_id, is_active);

create table if not exists public.social_accounts (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.users(id) on delete cascade,
    platform text not null,
    handle text not null,
    display_name text,
    encrypted_access_token text,
    encrypted_refresh_token text,
    token_expires_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (owner_id, platform, handle)
);

create index if not exists idx_social_accounts_owner on public.social_accounts(owner_id, platform);

create table if not exists public.posts (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.users(id) on delete cascade,
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
create index if not exists idx_posts_scheduled_for on public.posts(scheduled_for) where scheduled_for is not null;

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

create index if not exists idx_post_deliveries_owner on public.post_deliveries(owner_id, platform, status);

create table if not exists public.video_jobs (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references public.users(id) on delete cascade,
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

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists trg_users_updated_at on public.users;
create trigger trg_users_updated_at before update on public.users
for each row execute function public.set_updated_at();

drop trigger if exists trg_api_keys_updated_at on public.api_keys;
create trigger trg_api_keys_updated_at before update on public.api_keys
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
