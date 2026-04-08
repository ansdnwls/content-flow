# Supabase Bootstrap

1. Create a new Supabase project.
2. Open the SQL editor and run [01_schema.sql](C:\Users\y2k_w\projects\content-flow\infra\supabase\01_schema.sql).
3. Run [02_rls.sql](C:\Users\y2k_w\projects\content-flow\infra\supabase\02_rls.sql).
4. Add the values from `.env.example` to your Railway service variables or local `.env`.
5. Use `app.core.auth.build_api_key_record()` from a one-off script or admin task to generate and persist new API keys.

RLS note:
The `api_keys` table is intentionally closed to `authenticated` clients. The backend should use the Supabase service-role key for API key lookup and mutation. Service-role access bypasses RLS, while direct client traffic remains blocked.
