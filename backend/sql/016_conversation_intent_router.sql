-- Conversation intent routing, idempotency, and short-lived conversation state.

CREATE TABLE IF NOT EXISTS public.inbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    provider_message_id TEXT NOT NULL,
    message_type TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    detected_intent TEXT,
    confidence NUMERIC,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    retention_expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT inbound_messages_channel_provider_msg_id_key
        UNIQUE (channel, provider_message_id),
    CONSTRAINT inbound_messages_channel_check
        CHECK (channel IN ('whatsapp', 'meta_whatsapp', 'telegram')),
    CONSTRAINT inbound_messages_message_type_check
        CHECK (message_type IN ('text', 'voice')),
    CONSTRAINT inbound_messages_intent_check CHECK (
        detected_intent IS NULL OR detected_intent IN (
            'new_order', 'order_update', 'order_cancel', 'order_tracking',
            'price_enquiry', 'payment_query', 'business_support',
            'general_message', 'spam', 'uncertain'
        )
    ),
    CONSTRAINT inbound_messages_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT inbound_messages_processing_status_check CHECK (
        processing_status IN (
            'pending', 'classifying', 'classified', 'extracting',
            'awaiting_confirmation', 'needs_review', 'processed',
            'failed', 'skipped'
        )
    ),
    CONSTRAINT inbound_messages_retry_count_check CHECK (retry_count >= 0)
);

-- These clauses make the migration safe if an earlier draft was already applied.
ALTER TABLE public.inbound_messages
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS retention_expires_at TIMESTAMPTZ
        DEFAULT (NOW() + INTERVAL '30 days'),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE public.inbound_messages
SET retention_expires_at = created_at + INTERVAL '30 days'
WHERE retention_expires_at IS NULL;

CREATE TABLE IF NOT EXISTS public.customer_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'idle',
    pending_intent TEXT,
    draft_payload JSONB,
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT customer_conversations_shop_cust_chan_key
        UNIQUE (shop_id, customer_id, channel),
    CONSTRAINT customer_conversations_channel_check
        CHECK (channel IN ('whatsapp', 'meta_whatsapp', 'telegram')),
    CONSTRAINT customer_conversations_state_check CHECK (
        state IN (
            'idle', 'awaiting_order', 'collecting_details',
            'awaiting_confirmation', 'creating_order', 'order_created',
            'human_support'
        )
    )
);

CREATE OR REPLACE FUNCTION public.set_intent_router_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_inbound_messages_updated_at
    ON public.inbound_messages;
CREATE TRIGGER trg_inbound_messages_updated_at
BEFORE UPDATE ON public.inbound_messages
FOR EACH ROW EXECUTE FUNCTION public.set_intent_router_updated_at();

DROP TRIGGER IF EXISTS trg_customer_conversations_updated_at
    ON public.customer_conversations;
CREATE TRIGGER trg_customer_conversations_updated_at
BEFORE UPDATE ON public.customer_conversations
FOR EACH ROW EXECUTE FUNCTION public.set_intent_router_updated_at();

CREATE INDEX IF NOT EXISTS idx_inbound_messages_processing_retry
    ON public.inbound_messages(processing_status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_shop_created
    ON public.inbound_messages(shop_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_retention
    ON public.inbound_messages(retention_expires_at);
CREATE INDEX IF NOT EXISTS idx_customer_conversations_state
    ON public.customer_conversations(state);
CREATE INDEX IF NOT EXISTS idx_customer_conversations_expires_at
    ON public.customer_conversations(expires_at);

ALTER TABLE public.inbound_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_conversations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Shop owners can read their inbound_messages"
    ON public.inbound_messages;
CREATE POLICY "Shop owners can read their inbound_messages"
ON public.inbound_messages FOR SELECT
USING (
    auth.uid() IN (
        SELECT owner_id FROM public.shops WHERE id = inbound_messages.shop_id
    )
);

DROP POLICY IF EXISTS "Shop owners can insert inbound_messages"
    ON public.inbound_messages;
DROP POLICY IF EXISTS "Shop owners can update inbound_messages"
    ON public.inbound_messages;
DROP POLICY IF EXISTS "Service role has full access to inbound_messages"
    ON public.inbound_messages;
CREATE POLICY "Service role has full access to inbound_messages"
ON public.inbound_messages FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Shop owners can read their customer_conversations"
    ON public.customer_conversations;
CREATE POLICY "Shop owners can read their customer_conversations"
ON public.customer_conversations FOR SELECT
USING (
    auth.uid() IN (
        SELECT owner_id FROM public.shops WHERE id = customer_conversations.shop_id
    )
);

DROP POLICY IF EXISTS "Shop owners can insert customer_conversations"
    ON public.customer_conversations;
DROP POLICY IF EXISTS "Shop owners can update customer_conversations"
    ON public.customer_conversations;
DROP POLICY IF EXISTS "Service role has full access to customer_conversations"
    ON public.customer_conversations;
CREATE POLICY "Service role has full access to customer_conversations"
ON public.customer_conversations FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

NOTIFY pgrst, 'reload schema';
