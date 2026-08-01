-- Preserve restaurant fulfilment and item modifiers after Action Card approval.
-- All columns are additive and nullable/defaulted, so existing grocery rows
-- and API behavior remain unchanged.

ALTER TABLE public.orders
    ADD COLUMN IF NOT EXISTS fulfillment_type TEXT,
    ADD COLUMN IF NOT EXISTS table_number TEXT,
    ADD COLUMN IF NOT EXISTS special_instructions TEXT;

ALTER TABLE public.order_items
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'orders_fulfillment_type_check'
          AND conrelid = 'public.orders'::regclass
    ) THEN
        ALTER TABLE public.orders
            ADD CONSTRAINT orders_fulfillment_type_check
            CHECK (
                fulfillment_type IS NULL
                OR fulfillment_type IN ('delivery', 'takeaway', 'dine_in', 'not_specified')
            );
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';
