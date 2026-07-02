-- 009_twilio_whatsapp_intake.sql

CREATE TABLE IF NOT EXISTS public.customer_channels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
    customer_id uuid REFERENCES public.customers(id) ON DELETE CASCADE NOT NULL,
    channel text NOT NULL, -- 'telegram', 'whatsapp', 'web', 'phone'
    channel_user_id text NOT NULL,
    channel_chat_id text,
    phone text,
    display_name text,
    state text DEFAULT 'awaiting_name',
    profile_completed boolean DEFAULT false,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(shop_id, channel, channel_user_id)
);

CREATE INDEX IF NOT EXISTS idx_customer_channels_lookup 
ON public.customer_channels(shop_id, channel, channel_user_id);

DROP TRIGGER IF EXISTS update_customer_channels_updated_at ON public.customer_channels;
CREATE TRIGGER update_customer_channels_updated_at
    BEFORE UPDATE ON public.customer_channels
    FOR EACH ROW
    EXECUTE PROCEDURE update_shops_updated_at_column();

-- Enable RLS on customer_channels
ALTER TABLE public.customer_channels ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage customer channels of their shops" ON public.customer_channels;
CREATE POLICY "Users can manage customer channels of their shops"
    ON public.customer_channels FOR ALL
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()))
    WITH CHECK (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));

NOTIFY pgrst, 'reload schema';
