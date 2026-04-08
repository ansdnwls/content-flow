-- Add language and timezone columns to users table
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT 'ko',
  ADD COLUMN IF NOT EXISTS timezone text NOT NULL DEFAULT 'Asia/Seoul';

CREATE INDEX IF NOT EXISTS idx_users_language ON public.users (language);
