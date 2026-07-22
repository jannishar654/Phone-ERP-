-- Durable Meta WhatsApp webhook processing and connection health.
-- This migration is additive and preserves existing pilot connections.

ALTER TABLE public.whatsapp_connections
    ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS disconnected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_health_check_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'whatsapp_connections_failure_count_check'
    ) THEN
        ALTER TABLE public.whatsapp_connections
            ADD CONSTRAINT whatsapp_connections_failure_count_check
            CHECK (failure_count >= 0);
    END IF;
END $$;

UPDATE public.whatsapp_connections
SET connected_at = COALESCE(connected_at, created_at)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS public.whatsapp_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL DEFAULT 'meta_cloud',
    event_kind TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    connection_id UUID REFERENCES public.whatsapp_connections(id) ON DELETE SET NULL,
    shop_id UUID REFERENCES public.shops(id) ON DELETE CASCADE,
    waba_id TEXT,
    phone_number_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 6,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    last_error TEXT,
    retention_expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_webhook_events_provider_check
        CHECK (provider = 'meta_cloud'),
    CONSTRAINT whatsapp_webhook_events_kind_check
        CHECK (event_kind IN ('message', 'status')),
    CONSTRAINT whatsapp_webhook_events_status_check
        CHECK (processing_status IN (
            'pending', 'processing', 'retry', 'completed',
            'dead_letter', 'unroutable'
        )),
    CONSTRAINT whatsapp_webhook_events_attempts_check
        CHECK (attempts >= 0 AND max_attempts > 0),
    CONSTRAINT whatsapp_webhook_events_provider_event_key
        UNIQUE (provider, event_kind, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_webhook_events_claim
    ON public.whatsapp_webhook_events(processing_status, available_at, created_at);
CREATE INDEX IF NOT EXISTS idx_whatsapp_webhook_events_shop_created
    ON public.whatsapp_webhook_events(shop_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_whatsapp_webhook_events_retention
    ON public.whatsapp_webhook_events(retention_expires_at);

CREATE TABLE IF NOT EXISTS public.whatsapp_outbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL DEFAULT 'meta_cloud',
    connection_id UUID REFERENCES public.whatsapp_connections(id) ON DELETE SET NULL,
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    phone_number_id TEXT NOT NULL,
    provider_message_id TEXT,
    recipient_hash TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'text',
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    provider_error_code TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_outbound_messages_provider_check
        CHECK (provider = 'meta_cloud'),
    CONSTRAINT whatsapp_outbound_messages_type_check
        CHECK (message_type IN ('text', 'template')),
    CONSTRAINT whatsapp_outbound_messages_status_check
        CHECK (delivery_status IN (
            'pending', 'accepted', 'sent', 'delivered', 'read', 'failed'
        )),
    CONSTRAINT whatsapp_outbound_messages_provider_message_key
        UNIQUE (provider, provider_message_id)
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_outbound_messages_shop_created
    ON public.whatsapp_outbound_messages(shop_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_whatsapp_outbound_messages_status
    ON public.whatsapp_outbound_messages(delivery_status, updated_at DESC);

CREATE OR REPLACE FUNCTION public.set_meta_whatsapp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_whatsapp_webhook_events_updated_at
    ON public.whatsapp_webhook_events;
CREATE TRIGGER trg_whatsapp_webhook_events_updated_at
BEFORE UPDATE ON public.whatsapp_webhook_events
FOR EACH ROW EXECUTE FUNCTION public.set_meta_whatsapp_updated_at();

DROP TRIGGER IF EXISTS trg_whatsapp_outbound_messages_updated_at
    ON public.whatsapp_outbound_messages;
CREATE TRIGGER trg_whatsapp_outbound_messages_updated_at
BEFORE UPDATE ON public.whatsapp_outbound_messages
FOR EACH ROW EXECUTE FUNCTION public.set_meta_whatsapp_updated_at();

-- Atomically claims pending/retry events. Processing leases older than five
-- minutes are recoverable after a crashed worker or Render restart.
CREATE OR REPLACE FUNCTION public.claim_meta_whatsapp_events(p_limit INTEGER DEFAULT 10)
RETURNS SETOF public.whatsapp_webhook_events
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    WITH candidates AS (
        SELECT event.id
        FROM public.whatsapp_webhook_events AS event
        WHERE (
            (
                event.processing_status IN ('pending', 'retry')
                AND event.available_at <= NOW()
            ) OR (
                event.processing_status = 'processing'
                AND event.locked_at < NOW() - INTERVAL '5 minutes'
            )
        )
        AND event.attempts < event.max_attempts
        ORDER BY event.created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT LEAST(GREATEST(p_limit, 1), 50)
    )
    UPDATE public.whatsapp_webhook_events AS event
    SET processing_status = 'processing',
        attempts = event.attempts + 1,
        locked_at = NOW(),
        last_error = NULL
    FROM candidates
    WHERE event.id = candidates.id
    RETURNING event.*;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_meta_whatsapp_events(INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_meta_whatsapp_events(INTEGER) FROM anon;
REVOKE ALL ON FUNCTION public.claim_meta_whatsapp_events(INTEGER) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.claim_meta_whatsapp_events(INTEGER) TO service_role;

ALTER TABLE public.whatsapp_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_outbound_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role manages WhatsApp webhook events"
    ON public.whatsapp_webhook_events;
CREATE POLICY "Service role manages WhatsApp webhook events"
ON public.whatsapp_webhook_events FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Shop owners can read WhatsApp message status"
    ON public.whatsapp_outbound_messages;
CREATE POLICY "Shop owners can read WhatsApp message status"
ON public.whatsapp_outbound_messages FOR SELECT
USING (
    auth.uid() IN (
        SELECT owner_id FROM public.shops
        WHERE id = whatsapp_outbound_messages.shop_id
    )
);

DROP POLICY IF EXISTS "Service role manages WhatsApp message status"
    ON public.whatsapp_outbound_messages;
CREATE POLICY "Service role manages WhatsApp message status"
ON public.whatsapp_outbound_messages FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

NOTIFY pgrst, 'reload schema';
