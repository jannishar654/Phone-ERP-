-- 011_add_order_number.sql

-- Create the sequence for order numbers starting at 1001
CREATE SEQUENCE IF NOT EXISTS public.order_number_seq START WITH 1001;

-- Add the order_number column to orders table if it does not exist
ALTER TABLE public.orders 
ADD COLUMN IF NOT EXISTS order_number integer DEFAULT nextval('public.order_number_seq');

-- In case there are existing orders where order_number is null, update them
UPDATE public.orders
SET order_number = nextval('public.order_number_seq')
WHERE order_number IS NULL;

-- Add unique constraint if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE c.conname = 'orders_order_number_key' AND t.relname = 'orders'
    ) THEN
        ALTER TABLE public.orders
        ADD CONSTRAINT orders_order_number_key UNIQUE (order_number);
    END IF;
END $$;

-- Notify PostgREST to reload schema
NOTIFY pgrst, 'reload schema';
