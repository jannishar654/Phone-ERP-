-- 002_shops_and_customers.sql

-- Create shops table
CREATE TABLE IF NOT EXISTS public.shops (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id uuid REFERENCES auth.users(id) NOT NULL,
    name text NOT NULL,
    address text,
    phone text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- trigger to auto update updated_at on shops
CREATE OR REPLACE FUNCTION update_shops_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_shops_updated_at ON public.shops;
CREATE TRIGGER update_shops_updated_at
    BEFORE UPDATE ON public.shops
    FOR EACH ROW
    EXECUTE PROCEDURE update_shops_updated_at_column();

-- Create customers table
CREATE TABLE IF NOT EXISTS public.customers (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
    name text NOT NULL,
    phone text,
    address text,
    balance numeric DEFAULT 0.0,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(shop_id, phone)
);

DROP TRIGGER IF EXISTS update_customers_updated_at ON public.customers;
CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON public.customers
    FOR EACH ROW
    EXECUTE PROCEDURE update_shops_updated_at_column();

-- Enable RLS on shops
ALTER TABLE public.shops ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own shops" ON public.shops;
CREATE POLICY "Users can manage their own shops"
    ON public.shops FOR ALL
    USING (auth.uid() = owner_id)
    WITH CHECK (auth.uid() = owner_id);

-- Enable RLS on customers
ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage customers of their shops" ON public.customers;
CREATE POLICY "Users can manage customers of their shops"
    ON public.customers FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));
