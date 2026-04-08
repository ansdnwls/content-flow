# Backup and Recovery

## Scope

This repository now includes infrastructure-only backup tooling for Supabase database rows and Supabase Storage files:

- `scripts/backup_db.py`
- `scripts/restore_db.py`
- `scripts/backup_files.py`
- `.github/workflows/backup.yml`

The scripts do not modify `app/`. They are designed for operator-driven recovery and scheduled backups.

## Backup Cadence

- Database backup: daily at `02:00 KST` through GitHub Actions cron `0 17 * * *` (`17:00 UTC` on the previous day).
- Storage backup: same schedule as database backup.
- On-demand backup: run the workflow manually with `workflow_dispatch` before risky migrations or bulk deletes.
- Retention:
  - S3: manage lifecycle rules separately. Recommended minimum retention is `30 days`.
  - GitHub Artifacts fallback: default workflow retention is `14 days`.

## Backup Layout

Backups are written to `backups/{timestamp}/`.

- `db_manifest.json`: database backup manifest
- `db/*.json` or `db/*.json.gpg`: table exports
- `storage_manifest.json`: storage manifest
- `storage/{bucket}/...`: downloaded objects

Database backups use table-by-table JSON export. When `--encrypt` is enabled, each table file is encrypted with `gpg --symmetric` using AES-256.

## Required Secrets

For automation:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `BACKUP_GPG_PASSPHRASE`

Optional for S3 uploads:

- `BACKUP_S3_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `BACKUP_S3_PREFIX` as a repository variable

Optional for failure notifications:

- `BACKUP_ALERT_WEBHOOK_URL`

Optional storage bucket allow-list:

- `BACKUP_BUCKETS` as a repository variable, for example `media thumbnails videos`

## Manual Backup

Database only:

```bash
python scripts/backup_db.py --encrypt
```

Database with explicit directory:

```bash
python scripts/backup_db.py --output-dir backups/manual-20260409 --encrypt
```

Storage only:

```bash
python scripts/backup_files.py --output-dir backups/manual-20260409 --buckets media thumbnails videos
```

## Restore Procedure

Dry-run first:

```bash
python scripts/restore_db.py backups/20260409T170000Z --dry-run
```

Restore all backed-up tables:

```bash
python scripts/restore_db.py backups/20260409T170000Z
```

Restore selected tables only:

```bash
python scripts/restore_db.py backups/20260409T170000Z --tables users posts post_deliveries
```

Non-interactive restore:

```bash
python scripts/restore_db.py backups/20260409T170000Z --yes
```

## Restore Behavior

- The restore path verifies `db_manifest.json`.
- Each backup file is checksum-validated before restore.
- Encrypted backups require `BACKUP_GPG_PASSPHRASE` or `--passphrase`.
- Restore is non-destructive by default:
  - rows with `id` are restored through `upsert(on_conflict='id')`
  - rows without `id` are inserted
- This means deleted rows can be reinserted, but extra rows created after the backup are not removed automatically.

If a true point-in-time rollback is required, perform a controlled table truncate or use managed Postgres recovery outside this repository before running `restore_db.py`.

## Disaster Recovery Scenarios

### 1. Database corruption

1. Stop write traffic or place the app in maintenance mode.
2. Identify the last known-good backup bundle.
3. Run `restore_db.py --dry-run`.
4. Restore parent tables first if doing a partial recovery.
5. Verify counts in Supabase.
6. Resume write traffic.

### 2. Accidental delete

1. Find the nearest backup prior to the delete event.
2. Restore only the affected tables with `--tables`.
3. Validate foreign-key dependent tables such as `post_deliveries`, `workspace_members`, or `social_accounts`.
4. Audit application behavior before reopening access.

### 3. Storage bucket loss

1. Extract the backup bundle.
2. Inspect `storage_manifest.json`.
3. Re-upload the needed files to Supabase Storage using an operator script or dashboard tooling.
4. Validate media URLs referenced by database rows before resuming publishing jobs.

## RTO and RPO Targets

Recommended baseline targets for the current automation:

- `RPO`: `<= 24 hours`
  - Daily scheduled backups mean up to one day of data loss is possible between snapshots.
- `RTO`: `<= 4 hours`
  - Assumes an operator can identify the correct bundle, run dry-run validation, restore, and verify dependent services.

If the production requirement is stricter than `24h/4h`, daily GitHub Actions backups are not sufficient by themselves. Increase frequency and add managed database recovery controls at the platform level.

## Operational Notes

- Run a manual backup before schema migrations, mass imports, or destructive admin tasks.
- Test restore flow in a staging Supabase project at least once per quarter.
- Keep the GPG passphrase outside the repository and rotate it with the same discipline as service-role credentials.
- S3 is the preferred durable target. GitHub Artifacts are a fallback, not a long-term archive.
