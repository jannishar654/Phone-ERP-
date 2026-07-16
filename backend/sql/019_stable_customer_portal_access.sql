-- Make customer portal links stable and retry-safe while preserving hashed tokens.
CREATE OR REPLACE FUNCTION public.issue_customer_portal_magic_link(
    p_shop_id UUID,
    p_customer_id UUID,
    p_channel TEXT,
    p_token_hash TEXT,
    p_expires_at TIMESTAMPTZ
)
RETURNS UUID AS $$
DECLARE
    access_link_id UUID;
BEGIN
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
    )
    ON CONFLICT (token_hash) DO UPDATE SET
        expires_at = EXCLUDED.expires_at,
        used_at = NULL,
        revoked_at = NULL
    RETURNING id INTO access_link_id;

    UPDATE public.customer_portal_magic_links AS links
    SET revoked_at = NOW()
    WHERE links.shop_id = p_shop_id
      AND links.customer_id = p_customer_id
      AND links.channel = p_channel
      AND links.id <> access_link_id
      AND links.revoked_at IS NULL;

    RETURN access_link_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.exchange_customer_portal_magic_link(
    p_token_hash TEXT,
    p_session_hash TEXT,
    p_session_expires_at TIMESTAMPTZ
)
RETURNS TABLE(shop_id UUID, customer_id UUID) AS $$
DECLARE
    link_row public.customer_portal_magic_links%ROWTYPE;
BEGIN
    SELECT * INTO link_row
    FROM public.customer_portal_magic_links AS links
    WHERE links.token_hash = p_token_hash
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid_link';
    END IF;
    IF link_row.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'link_revoked';
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
    );

    RETURN QUERY SELECT link_row.shop_id, link_row.customer_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

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

NOTIFY pgrst, 'reload schema';
