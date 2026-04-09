# Supabase Migration Order

## Purpose

The application code expects more schema than the original `infra/supabase/01_schema.sql` provided. In particular:

- `009_add_user_language.sql` backfills user-account columns that the API already reads and updates.
- `013_missing_tables.sql` creates the previously missing tables and patches workspace-related columns on existing core tables.
- `011_ytboost.sql` remains the single source of truth for `ytboost_subscriptions`, `ytboost_shorts`, and `ytboost_channel_tones`.

## Recommended Order

Run these files in order on a blank database:

1. [01_schema.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/01_schema.sql)
2. [02_rls.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/02_rls.sql)
3. [009_add_user_language.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/009_add_user_language.sql)
4. [010_performance_indexes.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/010_performance_indexes.sql)
5. [011_ytboost.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/011_ytboost.sql)
6. [012_webhook_idempotency.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/012_webhook_idempotency.sql)
7. [013_missing_tables.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/013_missing_tables.sql)
8. [03_seed.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/03_seed.sql) if you need local sample data

## File Roles

- `01_schema.sql`: base tables that existed from the first Supabase bootstrap.
- `02_rls.sql`: initial RLS policies for the base tables.
- `009_add_user_language.sql`: adds missing `users` columns referenced by billing, privacy, onboarding, and workspace flows.
- `010_performance_indexes.sql`: optional performance indexes. This file now guards missing-table cases so it can run safely before `013`.
- `011_ytboost.sql`: ytboost tables only.
- `012_webhook_idempotency.sql`: idempotency retrofit for `webhook_deliveries`. This file now skips cleanly when the table is not present yet.
- `013_missing_tables.sql`: creates the missing non-ytboost tables, adds workspace columns to legacy core tables, adds indexes, triggers, and RLS.

## Dependency Notes

- `users` must exist before every child table in `013`.
- `workspaces` must be created before `workspace_members`.
- `workspaces` must exist before adding `users.default_workspace_id` and `workspace_id` foreign keys on `api_keys`, `social_accounts`, `posts`, and `video_jobs`.
- `webhooks` must exist before `webhook_deliveries`.
- `posts` must exist before `schedules`.
- `011_ytboost.sql` already owns all three ytboost tables; `013` intentionally does not recreate them.

## Known Inconsistencies Found

- The deployment instructions referenced `009_add_user_language.sql`, but that file was missing from the repository and had to be added.
- The analysis request referenced `migrations/010_ytboost_tables.sql`, but the repository only contains [011_ytboost.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/011_ytboost.sql).
- `010_performance_indexes.sql` and `012_webhook_idempotency.sql` previously assumed tables that were not yet created on a blank database; both were made idempotent for first-run bootstrap.
