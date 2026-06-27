-- 006_telegram_customers.sql

-- Safe alter for customers table to support telegram intake
ALTER TABLE public.customers
ADD COLUMN IF NOT EXISTS telegram_user_id text UNIQUE,
ADD COLUMN IF NOT EXISTS telegram_chat_id text,
ADD COLUMN IF NOT EXISTS default_address text,
ADD COLUMN IF NOT EXISTS profile_completed boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS telegram_state text;

-- Create an index for quick lookup by telegram user id
CREATE INDEX IF NOT EXISTS idx_customers_telegram_user_id ON public.customers(telegram_user_id);
