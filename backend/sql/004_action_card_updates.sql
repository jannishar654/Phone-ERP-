-- 004_action_card_updates.sql

-- Add shop_id and customer_id to action_cards to link them to the new data model

ALTER TABLE public.action_cards 
ADD COLUMN IF NOT EXISTS shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE;

ALTER TABLE public.action_cards 
ADD COLUMN IF NOT EXISTS customer_id uuid REFERENCES public.customers(id) ON DELETE SET NULL;

ALTER TABLE public.action_cards 
ADD COLUMN IF NOT EXISTS order_id uuid REFERENCES public.orders(id) ON DELETE SET NULL;

-- Enable RLS on action_cards
ALTER TABLE public.action_cards ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage action cards of their shops" ON public.action_cards;
CREATE POLICY "Users can manage action cards of their shops"
    ON public.action_cards FOR ALL
    USING (user_id = auth.uid() OR shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()))
    WITH CHECK (user_id = auth.uid() OR shop_id IN (SELECT id FROM public.shops WHERE owner_id = auth.uid()));
