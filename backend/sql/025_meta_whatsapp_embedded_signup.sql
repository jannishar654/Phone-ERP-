-- Multi-business Meta WhatsApp Embedded Signup foundation.
-- Additive: existing pilot connections and webhook routing remain unchanged.

ALTER TABLE public.whatsapp_connections
    ADD COLUMN IF NOT EXISTS meta_business_id TEXT,
    ADD COLUMN IF NOT EXISTS verified_name TEXT,
    ADD COLUMN IF NOT EXISTS granted_scopes JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS connected_by UUID,
    ADD COLUMN IF NOT EXISTS disconnected_by UUID;

ALTER TABLE public.whatsapp_connections
    DROP CONSTRAINT IF EXISTS whatsapp_connections_status_check;
ALTER TABLE public.whatsapp_connections
    ADD CONSTRAINT whatsapp_connections_status_check
    CHECK (status IN (
        'pending', 'active', 'reconnect_required', 'disconnected', 'error'
    ));

-- Phase one made provider + phone_number_id unique across every historical
-- row. That blocks a legitimate reconnect after the old row is disconnected.
-- Keep history, but enforce uniqueness only for live/routable connections.
ALTER TABLE public.whatsapp_connections
    DROP CONSTRAINT IF EXISTS whatsapp_connections_provider_phone_key;

-- Phase 2 currently supports one live Meta connection per PhoneERP shop and
-- one PhoneERP shop per WABA. These indexes also close concurrent-callback
-- races that application-level checks alone cannot prevent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_live_connection_per_shop
    ON public.whatsapp_connections(provider, shop_id)
    WHERE status IN ('pending', 'active', 'reconnect_required', 'error');
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_live_connection_per_phone
    ON public.whatsapp_connections(provider, phone_number_id)
    WHERE status IN ('pending', 'active', 'reconnect_required', 'error');
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_live_connection_per_waba
    ON public.whatsapp_connections(provider, waba_id)
    WHERE status IN ('pending', 'active', 'reconnect_required', 'error');

CREATE TABLE IF NOT EXISTS public.whatsapp_onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_hash TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    safe_error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_onboarding_sessions_status_check
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_onboarding_sessions_expiry
    ON public.whatsapp_onboarding_sessions(expires_at);

-- Secrets are deliberately separated from the owner-readable connection row.
CREATE TABLE IF NOT EXISTS public.whatsapp_connection_credentials (
    connection_id UUID PRIMARY KEY
        REFERENCES public.whatsapp_connections(id) ON DELETE CASCADE,
    encrypted_token TEXT NOT NULL,
    token_nonce TEXT NOT NULL,
    key_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_connection_credentials_key_version_check
        CHECK (key_version > 0)
);

CREATE TABLE IF NOT EXISTS public.whatsapp_connection_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES public.whatsapp_connections(id) ON DELETE SET NULL,
    actor_user_id UUID,
    action TEXT NOT NULL,
    safe_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_connection_audit_action_check
        CHECK (action IN (
            'onboarding_started', 'connection_activated', 'health_checked',
            'reconnect_required', 'connection_disconnected', 'onboarding_failed'
        ))
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_connection_audit_shop_created
    ON public.whatsapp_connection_audit_logs(shop_id, created_at DESC);

-- Atomically consumes a one-time state token. Only the service-role backend can
-- call this function, preventing callback replay and cross-owner consumption.
CREATE OR REPLACE FUNCTION public.consume_whatsapp_onboarding_session(
    p_state_hash TEXT,
    p_user_id UUID,
    p_shop_id UUID
)
RETURNS SETOF public.whatsapp_onboarding_sessions
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    UPDATE public.whatsapp_onboarding_sessions AS session
    SET status = 'processing', consumed_at = NOW()
    WHERE session.state_hash = p_state_hash
      AND session.user_id = p_user_id
      AND session.shop_id = p_shop_id
      AND session.status = 'pending'
      AND session.consumed_at IS NULL
      AND session.expires_at > NOW()
    RETURNING session.*;
END;
$$;

REVOKE ALL ON FUNCTION public.consume_whatsapp_onboarding_session(TEXT, UUID, UUID)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.consume_whatsapp_onboarding_session(TEXT, UUID, UUID)
    TO service_role;

ALTER TABLE public.whatsapp_onboarding_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_connection_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_connection_audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role manages WhatsApp onboarding sessions"
    ON public.whatsapp_onboarding_sessions;
CREATE POLICY "Service role manages WhatsApp onboarding sessions"
ON public.whatsapp_onboarding_sessions FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Service role manages WhatsApp credentials"
    ON public.whatsapp_connection_credentials;
CREATE POLICY "Service role manages WhatsApp credentials"
ON public.whatsapp_connection_credentials FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Shop owners can read WhatsApp connection audit logs"
    ON public.whatsapp_connection_audit_logs;
CREATE POLICY "Shop owners can read WhatsApp connection audit logs"
ON public.whatsapp_connection_audit_logs FOR SELECT
USING (
    auth.uid() IN (
        SELECT owner_id FROM public.shops
        WHERE id = whatsapp_connection_audit_logs.shop_id
    )
);

DROP POLICY IF EXISTS "Service role manages WhatsApp connection audit logs"
    ON public.whatsapp_connection_audit_logs;
CREATE POLICY "Service role manages WhatsApp connection audit logs"
ON public.whatsapp_connection_audit_logs FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

NOTIFY pgrst, 'reload schema';
