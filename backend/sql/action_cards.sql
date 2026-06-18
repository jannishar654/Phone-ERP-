-- action_cards.sql

CREATE TABLE IF NOT EXISTS public.action_cards (
    id text PRIMARY KEY,
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    customer_name text,
    customer_phone text,
    items jsonb DEFAULT '[]'::jsonb,
    delivery_address text,
    delivery_time text,
    delivery_time_raw text,
    delivery_time_normalized text,
    delivery_time_confidence numeric,
    delivery_time_warning text,
    risk_flags jsonb DEFAULT '[]'::jsonb,
    missing_fields jsonb DEFAULT '[]'::jsonb,
    validation_warnings jsonb DEFAULT '[]'::jsonb,
    payment_method text DEFAULT 'Not Specified',
    status text DEFAULT 'pending',
    source text DEFAULT 'text',
    message_type text DEFAULT 'ORDER',
    confidence numeric,
    stt_provider text,
    extraction_provider text,
    metadata jsonb DEFAULT '{}'::jsonb,
    transcript text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- trigger to auto update updated_at
CREATE OR REPLACE FUNCTION update_action_cards_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_action_cards_updated_at ON public.action_cards;

CREATE TRIGGER update_action_cards_updated_at
    BEFORE UPDATE ON public.action_cards
    FOR EACH ROW
    EXECUTE PROCEDURE update_action_cards_updated_at_column();
