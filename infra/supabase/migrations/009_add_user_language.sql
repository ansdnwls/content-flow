-- Backfill missing user-account columns used by the application layer.
-- This migration was referenced in deployment runbooks but missing from the repo.

alter table public.users
    add column if not exists stripe_customer_id text,
    add column if not exists stripe_subscription_id text,
    add column if not exists subscription_status text,
    add column if not exists current_period_end timestamptz,
    add column if not exists cancel_at_period_end boolean not null default false,
    add column if not exists email_verified boolean not null default false,
    add column if not exists email_verified_at timestamptz,
    add column if not exists onboarding_completed boolean not null default false,
    add column if not exists onboarding_steps jsonb not null default '{}'::jsonb,
    add column if not exists default_workspace_id uuid,
    add column if not exists language text not null default 'ko',
    add column if not exists timezone text not null default 'Asia/Seoul',
    add column if not exists data_processing_restricted boolean not null default false,
    add column if not exists deletion_scheduled_at timestamptz;
