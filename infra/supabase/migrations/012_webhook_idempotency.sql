alter table public.webhook_deliveries
    add column if not exists idempotency_key text;

update public.webhook_deliveries
set idempotency_key = 'legacy:' || id::text
where idempotency_key is null;

alter table public.webhook_deliveries
    alter column idempotency_key set not null;

create unique index if not exists idx_webhook_deliveries_idempotency_key
    on public.webhook_deliveries(idempotency_key);
