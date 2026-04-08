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

create index if not exists idx_ytboost_subscriptions_user
    on public.ytboost_subscriptions(user_id, youtube_channel_id);

create index if not exists idx_ytboost_shorts_user
    on public.ytboost_shorts(user_id, status, created_at desc);

create index if not exists idx_ytboost_shorts_source
    on public.ytboost_shorts(source_video_id, source_channel_id);

create index if not exists idx_ytboost_channel_tones_user
    on public.ytboost_channel_tones(user_id, youtube_channel_id);
