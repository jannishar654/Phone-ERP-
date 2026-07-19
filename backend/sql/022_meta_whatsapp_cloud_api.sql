-- Meta WhatsApp Cloud API tenant routing.
-- Access tokens remain in server-side secret storage and are never stored here.

CREATE TABLE IF NOT EXISTS public.whatsapp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'meta_cloud',
    waba_id TEXT NOT NULL,
    phone_number_id TEXT NOT NULL,
    display_phone_number TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    token_reference TEXT,
    last_webhook_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_connections_provider_check
        CHECK (provider IN ('meta_cloud')),
    CONSTRAINT whatsapp_connections_status_check
        CHECK (status IN ('pending', 'active', 'disconnected', 'error')),
    CONSTRAINT whatsapp_connections_provider_phone_key
        UNIQUE (provider, phone_number_id)
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_connections_shop
    ON public.whatsapp_connections(shop_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_connections_waba
    ON public.whatsapp_connections(waba_id);

CREATE OR REPLACE FUNCTION public.set_whatsapp_connection_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_whatsapp_connections_updated_at
    ON public.whatsapp_connections;
CREATE TRIGGER trg_whatsapp_connections_updated_at
BEFORE UPDATE ON public.whatsapp_connections
FOR EACH ROW EXECUTE FUNCTION public.set_whatsapp_connection_updated_at();

ALTER TABLE public.whatsapp_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Shop owners can read WhatsApp connections"
    ON public.whatsapp_connections;
CREATE POLICY "Shop owners can read WhatsApp connections"
ON public.whatsapp_connections FOR SELECT
USING (
    auth.uid() IN (
        SELECT owner_id FROM public.shops
        WHERE id = whatsapp_connections.shop_id
    )
);

DROP POLICY IF EXISTS "Service role manages WhatsApp connections"
    ON public.whatsapp_connections;
CREATE POLICY "Service role manages WhatsApp connections"
ON public.whatsapp_connections FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

NOTIFY pgrst, 'reload schema';
