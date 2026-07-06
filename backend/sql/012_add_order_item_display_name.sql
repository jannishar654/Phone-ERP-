-- Add display_name to order_items to persist matched canonical product name
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'order_items' 
        AND column_name = 'display_name'
    ) THEN
        ALTER TABLE order_items ADD COLUMN display_name VARCHAR(255);
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';
