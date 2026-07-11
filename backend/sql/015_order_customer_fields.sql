-- 015_order_customer_fields.sql

-- Add customer details directly to orders table to preserve them independent of the customers table
ALTER TABLE public.orders 
ADD COLUMN IF NOT EXISTS customer_name text;

ALTER TABLE public.orders 
ADD COLUMN IF NOT EXISTS customer_phone text;

-- Notify PostgREST to reload the schema so the new columns are available via the API
NOTIFY pgrst, 'reload schema';
