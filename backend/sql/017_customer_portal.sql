-- Secure customer portal access, lifecycle history, and owner-reviewed requests.

CREATE TABLE IF NOT EXISTS public.customer_portal_magic_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'meta_whatsapp', 'telegram')),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_portal_magic_customer
    ON public.customer_portal_magic_links(shop_id, customer_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.issue_customer_portal_magic_link(
    p_shop_id UUID,
    p_customer_id UUID,
    p_channel TEXT,
    p_token_hash TEXT,
    p_expires_at TIMESTAMPTZ
)
RETURNS UUID AS $$
DECLARE
    new_link_id UUID;
BEGIN
    -- Serialize link issuance for one customer/channel so concurrent webhook
    -- retries cannot revoke both newly-created links.
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            p_shop_id::TEXT || ':' || p_customer_id::TEXT || ':' || p_channel,
            0
        )
    );

    INSERT INTO public.customer_portal_magic_links(
        shop_id, customer_id, channel, token_hash, expires_at
    ) VALUES (
        p_shop_id, p_customer_id, p_channel, p_token_hash, p_expires_at
    ) RETURNING id INTO new_link_id;

    UPDATE public.customer_portal_magic_links
    SET revoked_at = NOW()
    WHERE shop_id = p_shop_id
      AND customer_id = p_customer_id
      AND channel = p_channel
      AND id <> new_link_id
      AND used_at IS NULL
      AND revoked_at IS NULL;

    RETURN new_link_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TABLE IF NOT EXISTS public.customer_portal_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_portal_session_customer
    ON public.customer_portal_sessions(shop_id, customer_id, expires_at DESC);

CREATE OR REPLACE FUNCTION public.exchange_customer_portal_magic_link(
    p_token_hash TEXT,
    p_session_hash TEXT,
    p_session_expires_at TIMESTAMPTZ
)
RETURNS TABLE(shop_id UUID, customer_id UUID) AS $$
DECLARE
    link_row public.customer_portal_magic_links%ROWTYPE;
    new_session_id UUID;
BEGIN
    SELECT * INTO link_row
    FROM public.customer_portal_magic_links AS links
    WHERE links.token_hash = p_token_hash
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid_link';
    END IF;
    IF link_row.used_at IS NOT NULL OR link_row.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'link_used';
    END IF;
    IF link_row.expires_at <= NOW() THEN
        RAISE EXCEPTION 'link_expired';
    END IF;

    UPDATE public.customer_portal_magic_links
    SET used_at = NOW()
    WHERE id = link_row.id;

    INSERT INTO public.customer_portal_sessions(
        shop_id, customer_id, token_hash, expires_at
    ) VALUES (
        link_row.shop_id, link_row.customer_id, p_session_hash, p_session_expires_at
    ) RETURNING id INTO new_session_id;

    UPDATE public.customer_portal_sessions AS sessions
    SET revoked_at = NOW()
    WHERE sessions.shop_id = link_row.shop_id
      AND sessions.customer_id = link_row.customer_id
      AND sessions.id <> new_session_id
      AND sessions.revoked_at IS NULL;

    RETURN QUERY SELECT link_row.shop_id, link_row.customer_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TABLE IF NOT EXISTS public.customer_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    order_id UUID REFERENCES public.orders(id) ON DELETE SET NULL,
    request_type TEXT NOT NULL CHECK (
        request_type IN ('repeat_order', 'cancel_order', 'change_order', 'support')
    ),
    message TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'approved', 'rejected', 'resolved')
    ),
    owner_note TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.customer_requests
    DROP CONSTRAINT IF EXISTS customer_requests_status_check;
ALTER TABLE public.customer_requests
    ADD CONSTRAINT customer_requests_status_check CHECK (
        status IN ('pending', 'processing', 'approved', 'rejected', 'resolved')
    );

CREATE INDEX IF NOT EXISTS idx_customer_requests_owner_queue
    ON public.customer_requests(shop_id, status, created_at DESC);
DROP INDEX IF EXISTS public.idx_customer_requests_no_duplicate_pending;
CREATE UNIQUE INDEX idx_customer_requests_no_duplicate_pending
    ON public.customer_requests(shop_id, customer_id, order_id, request_type)
    WHERE status IN ('pending', 'processing') AND order_id IS NOT NULL;

ALTER TABLE public.action_cards
    ADD COLUMN IF NOT EXISTS customer_request_id UUID
    REFERENCES public.customer_requests(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_action_cards_customer_request
    ON public.action_cards(customer_request_id)
    WHERE customer_request_id IS NOT NULL;

DROP TRIGGER IF EXISTS update_customer_requests_updated_at ON public.customer_requests;
CREATE TRIGGER update_customer_requests_updated_at
    BEFORE UPDATE ON public.customer_requests
    FOR EACH ROW EXECUTE PROCEDURE update_shops_updated_at_column();

CREATE OR REPLACE FUNCTION public.approve_customer_cancellation(
    p_request_id UUID,
    p_shop_id UUID,
    p_owner_note TEXT DEFAULT NULL
)
RETURNS public.customer_requests AS $$
DECLARE
    request_row public.customer_requests%ROWTYPE;
    order_status TEXT;
BEGIN
    SELECT * INTO request_row
    FROM public.customer_requests
    WHERE id = p_request_id
      AND shop_id = p_shop_id
      AND request_type = 'cancel_order'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'customer_request_not_found';
    END IF;
    IF request_row.status <> 'pending' THEN
        RAISE EXCEPTION 'customer_request_already_handled';
    END IF;

    SELECT lifecycle_status INTO order_status
    FROM public.orders
    WHERE id = request_row.order_id
      AND shop_id = request_row.shop_id
      AND customer_id = request_row.customer_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'order_not_found';
    END IF;
    IF order_status IN ('delivered', 'cancelled') THEN
        RAISE EXCEPTION 'order_cannot_be_cancelled';
    END IF;

    UPDATE public.orders
    SET lifecycle_status = 'cancelled', cancelled_at = NOW()
    WHERE id = request_row.order_id;

    UPDATE public.customer_requests
    SET status = 'approved', owner_note = p_owner_note, resolved_at = NOW()
    WHERE id = p_request_id
    RETURNING * INTO request_row;

    RETURN request_row;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TABLE IF NOT EXISTS public.order_status_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    lifecycle_status TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_status_events_order
    ON public.order_status_events(order_id, occurred_at ASC);

CREATE TABLE IF NOT EXISTS public.owner_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    action_card_id TEXT REFERENCES public.action_cards(id) ON DELETE CASCADE,
    customer_request_id UUID REFERENCES public.customer_requests(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL CHECK (
        notification_type IN ('new_order', 'order_reminder', 'customer_request')
    ),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (action_card_id IS NOT NULL OR customer_request_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_owner_notifications_due
    ON public.owner_notifications(shop_id, scheduled_at)
    WHERE acknowledged_at IS NULL AND dismissed_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_notifications_action_type
    ON public.owner_notifications(action_card_id, notification_type)
    WHERE action_card_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_notifications_request_type
    ON public.owner_notifications(customer_request_id, notification_type)
    WHERE customer_request_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.record_order_lifecycle_event()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.lifecycle_status IS DISTINCT FROM OLD.lifecycle_status THEN
        INSERT INTO public.order_status_events(shop_id, order_id, lifecycle_status, occurred_at)
        VALUES (
            NEW.shop_id,
            NEW.id,
            COALESCE(NEW.lifecycle_status, 'received'),
            COALESCE(NEW.updated_at, NOW())
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS record_order_lifecycle_event ON public.orders;
CREATE TRIGGER record_order_lifecycle_event
    AFTER INSERT OR UPDATE OF lifecycle_status ON public.orders
    FOR EACH ROW EXECUTE PROCEDURE public.record_order_lifecycle_event();

CREATE OR REPLACE FUNCTION public.queue_action_card_notifications()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status = 'pending' AND NEW.shop_id IS NOT NULL THEN
        INSERT INTO public.owner_notifications(
            shop_id, action_card_id, notification_type, title, message, scheduled_at
        ) VALUES
        (
            NEW.shop_id,
            NEW.id,
            'new_order',
            'New customer order',
            COALESCE(NEW.customer_name, 'A customer') || ' sent an order for review.',
            NOW()
        ),
        (
            NEW.shop_id,
            NEW.id,
            'order_reminder',
            'Order still waiting',
            'A customer order has been waiting for review for 5 minutes.',
            NOW() + INTERVAL '5 minutes'
        )
        ON CONFLICT DO NOTHING;
    ELSIF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status
          AND NEW.status <> 'pending' THEN
        UPDATE public.owner_notifications
        SET dismissed_at = COALESCE(dismissed_at, NOW())
        WHERE action_card_id = NEW.id
          AND acknowledged_at IS NULL
          AND dismissed_at IS NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS queue_action_card_notifications ON public.action_cards;
CREATE TRIGGER queue_action_card_notifications
    AFTER INSERT OR UPDATE OF status ON public.action_cards
    FOR EACH ROW EXECUTE PROCEDURE public.queue_action_card_notifications();

CREATE OR REPLACE FUNCTION public.queue_customer_request_notification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.owner_notifications(
            shop_id, customer_request_id, notification_type, title, message, scheduled_at
        ) VALUES (
            NEW.shop_id,
            NEW.id,
            'customer_request',
            'Customer request received',
            'A customer submitted a ' || REPLACE(NEW.request_type, '_', ' ') || ' request.',
            NOW()
        )
        ON CONFLICT DO NOTHING;
    ELSIF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status
          AND NEW.status NOT IN ('pending', 'processing') THEN
        UPDATE public.owner_notifications
        SET dismissed_at = COALESCE(dismissed_at, NOW())
        WHERE customer_request_id = NEW.id
          AND acknowledged_at IS NULL
          AND dismissed_at IS NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS queue_customer_request_notification ON public.customer_requests;
CREATE TRIGGER queue_customer_request_notification
    AFTER INSERT OR UPDATE OF status ON public.customer_requests
    FOR EACH ROW EXECUTE PROCEDURE public.queue_customer_request_notification();

ALTER TABLE public.customer_portal_magic_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_portal_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_status_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.owner_notifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Shop owners can read customer requests" ON public.customer_requests;
CREATE POLICY "Shop owners can read customer requests" ON public.customer_requests
    FOR SELECT USING (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    );

DROP POLICY IF EXISTS "Shop owners can update customer requests" ON public.customer_requests;
CREATE POLICY "Shop owners can update customer requests" ON public.customer_requests
    FOR UPDATE USING (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    ) WITH CHECK (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    );

DROP POLICY IF EXISTS "Shop owners can read order status events" ON public.order_status_events;
CREATE POLICY "Shop owners can read order status events" ON public.order_status_events
    FOR SELECT USING (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    );

DROP POLICY IF EXISTS "Shop owners can manage notifications" ON public.owner_notifications;
CREATE POLICY "Shop owners can manage notifications" ON public.owner_notifications
    FOR ALL USING (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    ) WITH CHECK (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    );

REVOKE ALL ON FUNCTION public.issue_customer_portal_magic_link(
    UUID, UUID, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.issue_customer_portal_magic_link(
    UUID, UUID, TEXT, TEXT, TIMESTAMPTZ
) TO service_role;

REVOKE ALL ON FUNCTION public.exchange_customer_portal_magic_link(
    TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.exchange_customer_portal_magic_link(
    TEXT, TEXT, TIMESTAMPTZ
) TO service_role;

REVOKE ALL ON FUNCTION public.approve_customer_cancellation(
    UUID, UUID, TEXT
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.approve_customer_cancellation(
    UUID, UUID, TEXT
) TO service_role;

NOTIFY pgrst, 'reload schema';
