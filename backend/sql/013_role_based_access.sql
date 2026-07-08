-- 013_role_based_access.sql

-- Staff Access Tokens Table
CREATE TABLE IF NOT EXISTS public.shop_staff_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'packer', 'delivery')),
    token_hash TEXT NOT NULL,
    label TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_staff_access_shop ON public.shop_staff_access(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_staff_access_hash ON public.shop_staff_access(token_hash);

-- Customer Order Public Links Table
CREATE TABLE IF NOT EXISTS public.order_public_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_public_links_order ON public.order_public_links(order_id);
CREATE INDEX IF NOT EXISTS idx_order_public_links_hash ON public.order_public_links(token_hash);

-- Deliveries Tracking Table
CREATE TABLE IF NOT EXISTS public.deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    assigned_to_name TEXT,
    assigned_to_phone TEXT,
    status TEXT CHECK (status IN ('assigned', 'in_progress', 'delivered', 'failed')),
    delivered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deliveries_shop ON public.deliveries(shop_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_order ON public.deliveries(order_id);

-- RLS for shop_staff_access
ALTER TABLE public.shop_staff_access ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Shop owners can manage staff access' AND tablename = 'shop_staff_access') THEN
        CREATE POLICY "Shop owners can manage staff access" ON public.shop_staff_access
            FOR ALL USING (
                auth.uid() IN (
                    SELECT owner_id FROM public.shops WHERE id = shop_staff_access.shop_id
                )
            );
    END IF;
END $$;

-- Allow system/backend to bypass RLS for token validation
-- (Assuming backend connects with service role or similar that bypasses RLS,
-- if not, we can add a specific policy for authenticated users if needed, 
-- but usually backend validation uses service_role key)

-- RLS for order_public_links
ALTER TABLE public.order_public_links ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Shop owners can manage public links' AND tablename = 'order_public_links') THEN
        CREATE POLICY "Shop owners can manage public links" ON public.order_public_links
            FOR ALL USING (
                auth.uid() IN (
                    SELECT owner_id FROM public.shops WHERE id = order_public_links.shop_id
                )
            );
    END IF;
END $$;

-- RLS for deliveries
ALTER TABLE public.deliveries ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Shop owners can manage deliveries' AND tablename = 'deliveries') THEN
        CREATE POLICY "Shop owners can manage deliveries" ON public.deliveries
            FOR ALL USING (
                auth.uid() IN (
                    SELECT owner_id FROM public.shops WHERE id = deliveries.shop_id
                )
            );
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';
