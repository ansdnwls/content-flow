#!/usr/bin/env bash
# Clean up E2E test data from the database.
# Only removes rows with e2e-prefixed IDs or test_ emails.

set -euo pipefail

DB_URL="${SUPABASE_DB_URL:-postgresql://localhost:5432/contentflow}"

echo "Cleaning E2E test data..."

psql "$DB_URL" <<'SQL'
BEGIN;

DELETE FROM public.social_accounts WHERE id LIKE 'e2eacct%';
DELETE FROM public.posts WHERE id LIKE 'e2epost%';
DELETE FROM public.api_keys WHERE id LIKE 'e2ekey%';
DELETE FROM public.users WHERE email LIKE 'test_%@contentflow.dev';

COMMIT;
SQL

echo "E2E cleanup complete."
