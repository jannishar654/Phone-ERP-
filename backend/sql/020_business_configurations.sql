-- Additive multi-business configuration foundation.
-- Operational order statuses remain unchanged for backward compatibility.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'business_type_enum') THEN
        CREATE TYPE public.business_type_enum AS ENUM (
            'grocery',
            'wholesale',
            'restaurant',
            'pharmacy',
            'bakery',
            'hardware',
            'general'
        );
    END IF;
END $$;

-- Make reruns safe if an earlier version created only part of the enum.
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'grocery';
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'wholesale';
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'restaurant';
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'pharmacy';
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'bakery';
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'hardware';
ALTER TYPE public.business_type_enum ADD VALUE IF NOT EXISTS 'general';

CREATE TABLE IF NOT EXISTS public.business_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    business_type public.business_type_enum NOT NULL DEFAULT 'grocery',
    display_name TEXT,
    required_order_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    optional_order_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    workflow_stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    extraction_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    terminology JSONB NOT NULL DEFAULT '{}'::jsonb,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT business_config_required_fields_array
        CHECK (jsonb_typeof(required_order_fields) = 'array'),
    CONSTRAINT business_config_optional_fields_array
        CHECK (jsonb_typeof(optional_order_fields) = 'array'),
    CONSTRAINT business_config_workflow_stages_array
        CHECK (jsonb_typeof(workflow_stages) = 'array'),
    CONSTRAINT business_config_extraction_context_object
        CHECK (jsonb_typeof(extraction_context) = 'object'),
    CONSTRAINT business_config_terminology_object
        CHECK (jsonb_typeof(terminology) = 'object'),
    CONSTRAINT business_config_settings_object
        CHECK (jsonb_typeof(settings) = 'object')
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_config_required_fields_array'
          AND conrelid = 'public.business_configurations'::regclass
    ) THEN
        ALTER TABLE public.business_configurations
            ADD CONSTRAINT business_config_required_fields_array
            CHECK (jsonb_typeof(required_order_fields) = 'array');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_config_optional_fields_array'
          AND conrelid = 'public.business_configurations'::regclass
    ) THEN
        ALTER TABLE public.business_configurations
            ADD CONSTRAINT business_config_optional_fields_array
            CHECK (jsonb_typeof(optional_order_fields) = 'array');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_config_workflow_stages_array'
          AND conrelid = 'public.business_configurations'::regclass
    ) THEN
        ALTER TABLE public.business_configurations
            ADD CONSTRAINT business_config_workflow_stages_array
            CHECK (jsonb_typeof(workflow_stages) = 'array');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_config_extraction_context_object'
          AND conrelid = 'public.business_configurations'::regclass
    ) THEN
        ALTER TABLE public.business_configurations
            ADD CONSTRAINT business_config_extraction_context_object
            CHECK (jsonb_typeof(extraction_context) = 'object');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_config_terminology_object'
          AND conrelid = 'public.business_configurations'::regclass
    ) THEN
        ALTER TABLE public.business_configurations
            ADD CONSTRAINT business_config_terminology_object
            CHECK (jsonb_typeof(terminology) = 'object');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_config_settings_object'
          AND conrelid = 'public.business_configurations'::regclass
    ) THEN
        ALTER TABLE public.business_configurations
            ADD CONSTRAINT business_config_settings_object
            CHECK (jsonb_typeof(settings) = 'object');
    END IF;
END $$;

-- Upgrade an earlier draft of this migration without losing data.
UPDATE public.business_configurations SET required_order_fields = '[]'::jsonb
WHERE required_order_fields IS NULL;
UPDATE public.business_configurations SET optional_order_fields = '[]'::jsonb
WHERE optional_order_fields IS NULL;
UPDATE public.business_configurations SET workflow_stages = '[]'::jsonb
WHERE workflow_stages IS NULL;
UPDATE public.business_configurations SET extraction_context = '{}'::jsonb
WHERE extraction_context IS NULL;
UPDATE public.business_configurations SET terminology = '{}'::jsonb
WHERE terminology IS NULL;
UPDATE public.business_configurations SET settings = '{}'::jsonb
WHERE settings IS NULL;
UPDATE public.business_configurations SET active = true WHERE active IS NULL;

ALTER TABLE public.business_configurations
    ALTER COLUMN required_order_fields SET NOT NULL,
    ALTER COLUMN optional_order_fields SET NOT NULL,
    ALTER COLUMN workflow_stages SET NOT NULL,
    ALTER COLUMN extraction_context SET NOT NULL,
    ALTER COLUMN terminology SET NOT NULL,
    ALTER COLUMN settings SET NOT NULL,
    ALTER COLUMN active SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_business_configurations_active_shop
    ON public.business_configurations(shop_id) WHERE active = true;

CREATE OR REPLACE FUNCTION public.update_business_configurations_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS update_business_configurations_updated_at
    ON public.business_configurations;
CREATE TRIGGER update_business_configurations_updated_at
    BEFORE UPDATE ON public.business_configurations
    FOR EACH ROW
    EXECUTE FUNCTION public.update_business_configurations_updated_at_column();

ALTER TABLE public.business_configurations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Shop owners can manage business configurations"
    ON public.business_configurations;
CREATE POLICY "Shop owners can manage business configurations"
    ON public.business_configurations
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.shops
            WHERE shops.id = business_configurations.shop_id
              AND shops.owner_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.shops
            WHERE shops.id = business_configurations.shop_id
              AND shops.owner_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Staff can read business configurations"
    ON public.business_configurations;
CREATE POLICY "Staff can read business configurations"
    ON public.business_configurations
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.shop_members
            WHERE shop_members.shop_id = business_configurations.shop_id
              AND shop_members.user_id = auth.uid()
              AND shop_members.status = 'active'
        )
    );

NOTIFY pgrst, 'reload schema';
