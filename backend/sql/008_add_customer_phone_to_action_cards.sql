-- Add customer_phone column to action_cards if it doesn't exist
ALTER TABLE public.action_cards ADD COLUMN IF NOT EXISTS customer_phone text;
