-- Controlled customer amendments for unconverted Action Cards.
ALTER TABLE public.action_cards
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE OR REPLACE FUNCTION public.update_action_cards_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_action_cards_updated_at ON public.action_cards;
CREATE TRIGGER update_action_cards_updated_at
    BEFORE UPDATE ON public.action_cards
    FOR EACH ROW EXECUTE PROCEDURE update_action_cards_updated_at_column();

CREATE TABLE IF NOT EXISTS public.customer_order_amendments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.customers(id) ON DELETE CASCADE,
    action_card_id TEXT REFERENCES public.action_cards(id) ON DELETE CASCADE,
    order_id UUID REFERENCES public.orders(id) ON DELETE CASCADE,
    amendment_type TEXT NOT NULL CHECK (
        amendment_type IN ('draft_edit', 'draft_cancel', 'change_request')
    ),
    before_snapshot JSONB NOT NULL DEFAULT '{}'::JSONB,
    after_snapshot JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((action_card_id IS NOT NULL)::INTEGER + (order_id IS NOT NULL)::INTEGER = 1)
);

CREATE INDEX IF NOT EXISTS idx_customer_order_amendments_card
    ON public.customer_order_amendments(action_card_id, created_at DESC)
    WHERE action_card_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customer_order_amendments_order
    ON public.customer_order_amendments(order_id, created_at DESC)
    WHERE order_id IS NOT NULL;

ALTER TABLE public.customer_order_amendments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Shop owners can read customer amendments"
    ON public.customer_order_amendments;
CREATE POLICY "Shop owners can read customer amendments"
    ON public.customer_order_amendments FOR SELECT USING (
        shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid())
    );

CREATE OR REPLACE FUNCTION public.update_customer_action_card_draft(
    p_action_card_id TEXT,
    p_shop_id UUID,
    p_customer_id UUID,
    p_expected_revision INTEGER,
    p_items JSONB,
    p_delivery_address TEXT,
    p_delivery_time TEXT
)
RETURNS public.action_cards AS $$
DECLARE
    existing public.action_cards%ROWTYPE;
    updated public.action_cards%ROWTYPE;
BEGIN
    SELECT * INTO existing
    FROM public.action_cards
    WHERE id = p_action_card_id
      AND shop_id = p_shop_id
      AND customer_id = p_customer_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'action_card_not_found';
    END IF;
    IF existing.order_id IS NOT NULL OR existing.status <> 'pending' THEN
        RAISE EXCEPTION 'action_card_not_editable';
    END IF;
    IF existing.revision <> p_expected_revision THEN
        RAISE EXCEPTION 'action_card_revision_conflict';
    END IF;
    IF jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'action_card_items_required';
    END IF;

    UPDATE public.action_cards
    SET items = p_items,
        delivery_address = NULLIF(BTRIM(p_delivery_address), ''),
        delivery_time = NULLIF(BTRIM(p_delivery_time), ''),
        status = 'pending',
        revision = revision + 1,
        updated_at = NOW(),
        metadata = COALESCE(metadata, '{}'::JSONB) || jsonb_build_object(
            'customer_last_edited_at', NOW(),
            'customer_revision', existing.revision + 1
        )
    WHERE id = existing.id
    RETURNING * INTO updated;

    INSERT INTO public.customer_order_amendments(
        shop_id, customer_id, action_card_id, amendment_type,
        before_snapshot, after_snapshot
    ) VALUES (
        p_shop_id, p_customer_id, existing.id, 'draft_edit',
        jsonb_build_object(
            'items', existing.items,
            'delivery_address', existing.delivery_address,
            'delivery_time', existing.delivery_time,
            'status', existing.status,
            'revision', existing.revision
        ),
        jsonb_build_object(
            'items', updated.items,
            'delivery_address', updated.delivery_address,
            'delivery_time', updated.delivery_time,
            'status', updated.status,
            'revision', updated.revision
        )
    );

    UPDATE public.owner_notifications
    SET title = 'Customer updated an order',
        message = COALESCE(updated.customer_name, 'A customer') ||
            ' updated an order that needs review.',
        scheduled_at = NOW(),
        acknowledged_at = NULL,
        dismissed_at = NULL
    WHERE action_card_id = existing.id
      AND notification_type = 'new_order';
    IF NOT FOUND THEN
        INSERT INTO public.owner_notifications(
            shop_id, action_card_id, notification_type, title, message, scheduled_at
        ) VALUES (
            p_shop_id, existing.id, 'new_order', 'Customer updated an order',
            COALESCE(updated.customer_name, 'A customer') ||
                ' updated an order that needs review.',
            NOW()
        );
    END IF;

    UPDATE public.owner_notifications
    SET title = 'Updated order still waiting',
        message = 'A customer-updated order has been waiting for review for 5 minutes.',
        scheduled_at = NOW() + INTERVAL '5 minutes',
        acknowledged_at = NULL,
        dismissed_at = NULL
    WHERE action_card_id = existing.id
      AND notification_type = 'order_reminder';
    IF NOT FOUND THEN
        INSERT INTO public.owner_notifications(
            shop_id, action_card_id, notification_type, title, message, scheduled_at
        ) VALUES (
            p_shop_id, existing.id, 'order_reminder',
            'Updated order still waiting',
            'A customer-updated order has been waiting for review for 5 minutes.',
            NOW() + INTERVAL '5 minutes'
        );
    END IF;

    RETURN updated;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE ALL ON FUNCTION public.update_customer_action_card_draft(
    TEXT, UUID, UUID, INTEGER, JSONB, TEXT, TEXT
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.update_customer_action_card_draft(
    TEXT, UUID, UUID, INTEGER, JSONB, TEXT, TEXT
) TO service_role;

NOTIFY pgrst, 'reload schema';
