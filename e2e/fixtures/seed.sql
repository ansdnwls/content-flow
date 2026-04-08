-- E2E test seed data
-- Run before E2E tests to populate test users and data

-- Test users (free, build, scale plans)
INSERT INTO public.users (id, email, full_name, plan, email_verified, language)
VALUES
  ('e2e00000-0000-0000-0000-000000000001', 'test_free@contentflow.dev', 'Free Tester', 'free', true, 'en'),
  ('e2e00000-0000-0000-0000-000000000002', 'test_build@contentflow.dev', 'Build Tester', 'build', true, 'en'),
  ('e2e00000-0000-0000-0000-000000000003', 'test_scale@contentflow.dev', 'Scale Tester', 'scale', true, 'en')
ON CONFLICT (email) DO UPDATE SET plan = EXCLUDED.plan, email_verified = true;

-- API keys for test users (pre-hashed; in real setup use proper hashing)
INSERT INTO public.api_keys (id, user_id, key_prefix, hashed_key, name, is_active)
VALUES
  ('e2ekey00-0000-0000-0000-000000000001', 'e2e00000-0000-0000-0000-000000000001', 'cf_live', 'e2e_hash_free', 'E2E Free Key', true),
  ('e2ekey00-0000-0000-0000-000000000002', 'e2e00000-0000-0000-0000-000000000002', 'cf_live', 'e2e_hash_build', 'E2E Build Key', true),
  ('e2ekey00-0000-0000-0000-000000000003', 'e2e00000-0000-0000-0000-000000000003', 'cf_live', 'e2e_hash_scale', 'E2E Scale Key', true)
ON CONFLICT (id) DO NOTHING;

-- Sample posts
INSERT INTO public.posts (id, owner_id, content, platforms, status)
VALUES
  ('e2epost0-0000-0000-0000-000000000001', 'e2e00000-0000-0000-0000-000000000001', 'E2E sample post 1', '{"x_twitter","linkedin"}', 'published'),
  ('e2epost0-0000-0000-0000-000000000002', 'e2e00000-0000-0000-0000-000000000001', 'E2E sample post 2', '{"youtube"}', 'scheduled')
ON CONFLICT (id) DO NOTHING;

-- Sample social accounts
INSERT INTO public.social_accounts (id, user_id, platform, platform_user_id, username, access_token_enc)
VALUES
  ('e2eacct0-0000-0000-0000-000000000001', 'e2e00000-0000-0000-0000-000000000001', 'youtube', 'yt_test_001', '@e2e_tester', 'enc_mock_token'),
  ('e2eacct0-0000-0000-0000-000000000002', 'e2e00000-0000-0000-0000-000000000001', 'x_twitter', 'tw_test_001', '@e2e_twitter', 'enc_mock_token')
ON CONFLICT (id) DO NOTHING;
