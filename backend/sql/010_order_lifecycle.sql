-- 010_order_lifecycle.sql

-- Add lifecycle_status and timestamp columns to orders table safely
ALTER TABLE public.orders 
ADD COLUMN IF NOT EXISTS lifecycle_status text,
ADD COLUMN IF NOT EXISTS packed_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS out_for_delivery_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS delivered_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS cancelled_at timestamp with time zone;

-- Create an index for quick filtering of orders by shop and lifecycle_status
CREATE INDEX IF NOT EXISTS idx_orders_shop_lifecycle 
ON public.orders(shop_id, lifecycle_status);

-- Safely add check constraint for allowed statuses
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE c.conname = 'orders_lifecycle_status_check' AND t.relname = 'orders'
    ) THEN
        ALTER TABLE public.orders 
        ADD CONSTRAINT orders_lifecycle_status_check 
        CHECK (lifecycle_status IS NULL OR lifecycle_status IN ('pending_review', 'packing', 'out_for_delivery', 'delivered', 'cancelled'));
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';
