-- Add confidence_score, confidence_label, confidence_reasons to action_cards

ALTER TABLE public.action_cards 
ADD COLUMN IF NOT EXISTS confidence_score integer,
ADD COLUMN IF NOT EXISTS confidence_label text,
ADD COLUMN IF NOT EXISTS confidence_reasons jsonb DEFAULT '[]'::jsonb;
