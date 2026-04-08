alter table public.users enable row level security;
alter table public.api_keys enable row level security;
alter table public.social_accounts enable row level security;
alter table public.posts enable row level security;
alter table public.post_deliveries enable row level security;
alter table public.video_jobs enable row level security;
alter table public.webhooks enable row level security;

drop policy if exists "users_self_select" on public.users;
create policy "users_self_select"
on public.users
for select
to authenticated
using (id = auth.uid());

drop policy if exists "users_self_update" on public.users;
create policy "users_self_update"
on public.users
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "api_keys_service_role_only" on public.api_keys;
create policy "api_keys_service_role_only"
on public.api_keys
for all
to authenticated
using (false)
with check (false);

drop policy if exists "social_accounts_owner_access" on public.social_accounts;
create policy "social_accounts_owner_access"
on public.social_accounts
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

drop policy if exists "posts_owner_access" on public.posts;
create policy "posts_owner_access"
on public.posts
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

drop policy if exists "post_deliveries_owner_access" on public.post_deliveries;
create policy "post_deliveries_owner_access"
on public.post_deliveries
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

drop policy if exists "video_jobs_owner_access" on public.video_jobs;
create policy "video_jobs_owner_access"
on public.video_jobs
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

drop policy if exists "webhooks_owner_access" on public.webhooks;
create policy "webhooks_owner_access"
on public.webhooks
for all
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());
