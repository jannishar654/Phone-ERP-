-- Fix ambiguous output-column references in the customer portal exchange RPC.
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

    UPDATE public.customer_portal_magic_links AS links
    SET used_at = NOW()
    WHERE links.id = link_row.id;

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

REVOKE ALL ON FUNCTION public.exchange_customer_portal_magic_link(
    TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.exchange_customer_portal_magic_link(
    TEXT, TEXT, TIMESTAMPTZ
) TO service_role;

NOTIFY pgrst, 'reload schema';
