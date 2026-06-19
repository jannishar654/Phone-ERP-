-- Supabase migration for voice recordings

-- Create voice_recordings table
CREATE TABLE IF NOT EXISTS public.voice_recordings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth.users(id) NOT NULL,
    action_card_id text,
    storage_path text NOT NULL,
    mime_type text NOT NULL,
    duration_seconds numeric,
    consent_for_evaluation boolean NOT NULL DEFAULT false,
    pipeline text,
    transcript text,
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

-- Enable RLS
ALTER TABLE public.voice_recordings ENABLE ROW LEVEL SECURITY;

-- Do not store anything without consent (rerunnable safely)
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c 
        JOIN pg_class t ON c.conrelid = t.oid 
        WHERE c.conname = 'consent_required' AND t.relname = 'voice_recordings'
    ) THEN 
        ALTER TABLE public.voice_recordings ADD CONSTRAINT consent_required CHECK (consent_for_evaluation = true); 
    END IF; 
END $$;

DROP POLICY IF EXISTS "Users can insert their own voice recordings" ON public.voice_recordings;
CREATE POLICY "Users can insert their own voice recordings"
    ON public.voice_recordings FOR INSERT
    WITH CHECK (auth.uid() = user_id AND consent_for_evaluation = true);

DROP POLICY IF EXISTS "Users can view their own voice recordings" ON public.voice_recordings;
CREATE POLICY "Users can view their own voice recordings"
    ON public.voice_recordings FOR SELECT
    USING (auth.uid() = user_id AND deleted_at IS NULL);

DROP POLICY IF EXISTS "Users can update their own voice recordings" ON public.voice_recordings;
CREATE POLICY "Users can update their own voice recordings"
    ON public.voice_recordings FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id AND consent_for_evaluation = true);

DROP POLICY IF EXISTS "Users can delete their own voice recordings" ON public.voice_recordings;
CREATE POLICY "Users can delete their own voice recordings"
    ON public.voice_recordings FOR DELETE
    USING (auth.uid() = user_id);

-- Ensure bucket exists and is private
INSERT INTO storage.buckets (id, name, public)
VALUES ('voice-recordings', 'voice-recordings', false)
ON CONFLICT (id) DO UPDATE SET public = false;

-- Storage bucket policies
DROP POLICY IF EXISTS "Users can upload their own audio" ON storage.objects;
CREATE POLICY "Users can upload their own audio"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'voice-recordings' AND auth.uid()::text = (storage.foldername(name))[1]);

DROP POLICY IF EXISTS "Users can view their own audio" ON storage.objects;
CREATE POLICY "Users can view their own audio"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'voice-recordings' AND auth.uid()::text = (storage.foldername(name))[1]);

DROP POLICY IF EXISTS "Users can delete their own audio" ON storage.objects;
CREATE POLICY "Users can delete their own audio"
    ON storage.objects FOR DELETE
    USING (bucket_id = 'voice-recordings' AND auth.uid()::text = (storage.foldername(name))[1]);
