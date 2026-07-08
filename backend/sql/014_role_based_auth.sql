-- Additive migration for role-based authentication and invites

-- Shop Members Table
CREATE TABLE IF NOT EXISTS public.shop_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'packer', 'delivery')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_members_shop ON public.shop_members(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_members_user ON public.shop_members(user_id);
-- Ensure a user can only have one active role per shop
CREATE UNIQUE INDEX IF NOT EXISTS idx_shop_members_unique_user_shop ON public.shop_members(shop_id, user_id) WHERE status = 'active';

-- Staff Invites Table
CREATE TABLE IF NOT EXISTS public.staff_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('packer', 'delivery')),
    invite_code_hash TEXT NOT NULL,
    label TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    used_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staff_invites_shop ON public.staff_invites(shop_id);
CREATE INDEX IF NOT EXISTS idx_staff_invites_hash ON public.staff_invites(invite_code_hash);

-- RLS for shop_members
ALTER TABLE public.shop_members ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    -- Owners can manage all members in their shop
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Shop owners can manage members' AND tablename = 'shop_members') THEN
        CREATE POLICY "Shop owners can manage members" ON public.shop_members
            FOR ALL USING (
                auth.uid() IN (
                    SELECT owner_id FROM public.shops WHERE id = shop_members.shop_id
                )
            );
    END IF;
    
    -- Users can read their own memberships
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can read own memberships' AND tablename = 'shop_members') THEN
        CREATE POLICY "Users can read own memberships" ON public.shop_members
            FOR SELECT USING (
                auth.uid() = user_id
            );
    END IF;
END $$;

-- RLS for staff_invites
ALTER TABLE public.staff_invites ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Shop owners can manage invites' AND tablename = 'staff_invites') THEN
        CREATE POLICY "Shop owners can manage invites" ON public.staff_invites
            FOR ALL USING (
                auth.uid() IN (
                    SELECT owner_id FROM public.shops WHERE id = staff_invites.shop_id
                )
            );
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';
