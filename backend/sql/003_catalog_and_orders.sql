-- 003_catalog_and_orders.sql

-- Upgrade products to catalog_items
-- We will add shop_id to products and rename it conceptually to catalog_items, or create a new table.
-- Let's create catalog_items for clarity, keeping it backward compatible if someone uses products.

CREATE TABLE IF NOT EXISTS public.catalog_items (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
    canonical_name text NOT NULL,
    display_name text NOT NULL,
    english_name text,
    base_price numeric NOT NULL DEFAULT 0.0,
    unit text,
    category text,
    active boolean DEFAULT true,
    in_stock boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(shop_id, canonical_name)
);

DROP TRIGGER IF EXISTS update_catalog_items_updated_at ON public.catalog_items;
CREATE TRIGGER update_catalog_items_updated_at
    BEFORE UPDATE ON public.catalog_items
    FOR EACH ROW
    EXECUTE PROCEDURE update_shops_updated_at_column();

-- Modify product_aliases to link to catalog_items
ALTER TABLE public.product_aliases 
ADD COLUMN IF NOT EXISTS catalog_item_id uuid REFERENCES public.catalog_items(id) ON DELETE CASCADE;

ALTER TABLE public.product_aliases 
ADD COLUMN IF NOT EXISTS shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE;

-- Create orders table
CREATE TABLE IF NOT EXISTS public.orders (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
    customer_id uuid REFERENCES public.customers(id) ON DELETE SET NULL,
    action_card_id text REFERENCES public.action_cards(id) ON DELETE SET NULL,
    total_amount numeric NOT NULL DEFAULT 0.0,
    status text DEFAULT 'pending', -- pending, completed, cancelled
    delivery_address text,
    delivery_time timestamp with time zone,
    payment_method text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

DROP TRIGGER IF EXISTS update_orders_updated_at ON public.orders;
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON public.orders
    FOR EACH ROW
    EXECUTE PROCEDURE update_shops_updated_at_column();

-- Create order_items table
CREATE TABLE IF NOT EXISTS public.order_items (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    order_id uuid REFERENCES public.orders(id) ON DELETE CASCADE NOT NULL,
    catalog_item_id uuid REFERENCES public.catalog_items(id) ON DELETE SET NULL,
    raw_name text,
    quantity numeric NOT NULL,
    unit text,
    unit_price numeric NOT NULL,
    line_total numeric NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS on catalog_items
ALTER TABLE public.catalog_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage catalog of their shops" ON public.catalog_items;
CREATE POLICY "Users can manage catalog of their shops"
    ON public.catalog_items FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));

-- Enable RLS on orders
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage orders of their shops" ON public.orders;
CREATE POLICY "Users can manage orders of their shops"
    ON public.orders FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));

-- Enable RLS on order_items
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage order_items of their shops" ON public.order_items;
CREATE POLICY "Users can manage order_items of their shops"
    ON public.order_items FOR ALL
    USING (order_id IN (SELECT id FROM public.orders WHERE shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())))
    WITH CHECK (order_id IN (SELECT id FROM public.orders WHERE shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())));

-- Enable RLS on product_aliases
ALTER TABLE public.product_aliases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage aliases of their shops" ON public.product_aliases;
CREATE POLICY "Users can manage aliases of their shops"
    ON public.product_aliases FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));
