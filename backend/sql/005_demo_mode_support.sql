-- 005_demo_mode_support.sql

-- Make owner_id nullable to support demo shops without auth.users FK
ALTER TABLE public.shops ALTER COLUMN owner_id DROP NOT NULL;

-- Update RLS on shops
DROP POLICY IF EXISTS "Users can manage their own shops" ON public.shops;
CREATE POLICY "Users can manage their own shops"
    ON public.shops FOR ALL
    USING (auth.uid() = owner_id OR owner_id IS NULL)
    WITH CHECK (auth.uid() = owner_id OR owner_id IS NULL);

-- Update RLS on customers
DROP POLICY IF EXISTS "Users can manage customers of their shops" ON public.customers;
CREATE POLICY "Users can manage customers of their shops"
    ON public.customers FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL));

-- Update RLS on catalog_items
DROP POLICY IF EXISTS "Users can manage catalog of their shops" ON public.catalog_items;
CREATE POLICY "Users can manage catalog of their shops"
    ON public.catalog_items FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL));

-- Update RLS on orders
DROP POLICY IF EXISTS "Users can manage orders of their shops" ON public.orders;
CREATE POLICY "Users can manage orders of their shops"
    ON public.orders FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL));

-- Update RLS on order_items
DROP POLICY IF EXISTS "Users can manage order_items of their shops" ON public.order_items;
CREATE POLICY "Users can manage order_items of their shops"
    ON public.order_items FOR ALL
    USING (order_id IN (SELECT id FROM public.orders WHERE shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL)))
    WITH CHECK (order_id IN (SELECT id FROM public.orders WHERE shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL)));

-- Update RLS on product_aliases
DROP POLICY IF EXISTS "Users can manage aliases of their shops" ON public.product_aliases;
CREATE POLICY "Users can manage aliases of their shops"
    ON public.product_aliases FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid() OR owner_id IS NULL));
