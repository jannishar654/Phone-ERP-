-- 026_multi_business_telegram.sql
-- Per-business Telegram bots with encrypted server-side credentials.

CREATE TABLE IF NOT EXISTS public.telegram_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id uuid NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    bot_id text NOT NULL,
    bot_username text,
    bot_display_name text,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'error', 'disconnected')),
    token_reference text,
    webhook_secret_hash text NOT NULL,
    connected_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    disconnected_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    connected_at timestamptz,
    disconnected_at timestamptz,
    last_webhook_at timestamptz,
    last_health_check_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT telegram_connections_shop_unique UNIQUE (shop_id),
    CONSTRAINT telegram_connections_bot_unique UNIQUE (bot_id)
);

CREATE INDEX IF NOT EXISTS idx_telegram_connections_active_bot
    ON public.telegram_connections(bot_id)
    WHERE status = 'active';

DROP TRIGGER IF EXISTS update_telegram_connections_updated_at
    ON public.telegram_connections;
CREATE TRIGGER update_telegram_connections_updated_at
    BEFORE UPDATE ON public.telegram_connections
    FOR EACH ROW EXECUTE PROCEDURE update_shops_updated_at_column();

CREATE TABLE IF NOT EXISTS public.telegram_connection_credentials (
    connection_id uuid PRIMARY KEY
        REFERENCES public.telegram_connections(id) ON DELETE CASCADE,
    encrypted_token text NOT NULL,
    token_nonce text NOT NULL,
    key_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS update_telegram_connection_credentials_updated_at
    ON public.telegram_connection_credentials;
CREATE TRIGGER update_telegram_connection_credentials_updated_at
    BEFORE UPDATE ON public.telegram_connection_credentials
    FOR EACH ROW EXECUTE PROCEDURE update_shops_updated_at_column();

CREATE TABLE IF NOT EXISTS public.telegram_connection_audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id uuid NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    connection_id uuid REFERENCES public.telegram_connections(id) ON DELETE SET NULL,
    actor_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    action text NOT NULL,
    safe_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.telegram_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telegram_connection_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telegram_connection_audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Owners can view Telegram connections" ON public.telegram_connections;
CREATE POLICY "Owners can view Telegram connections"
    ON public.telegram_connections FOR SELECT
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));

DROP POLICY IF EXISTS "Owners can view Telegram audit logs" ON public.telegram_connection_audit_logs;
CREATE POLICY "Owners can view Telegram audit logs"
    ON public.telegram_connection_audit_logs FOR SELECT
    USING (shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));

-- No client policy is intentionally created for credentials. Only the backend
-- service role may read or mutate encrypted bot tokens.

NOTIFY pgrst, 'reload schema';
