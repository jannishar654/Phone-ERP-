import { supabase } from './supabase/client';

export type VoiceRecordingResult = {
  success: boolean;
  message?: string;
  error?: string;
  storagePath?: string;
};

export async function saveVoiceRecording(
  audioBlob: Blob,
  extension: string,
  durationSeconds: number,
  cardId: string,
  consent: boolean,
  pipeline: string,
  transcript: string
): Promise<VoiceRecordingResult> {
  if (!consent) {
    return { success: false, error: 'Consent is required to save recording.' };
  }

  if (!supabase) {
    return { success: false, error: 'Supabase client is not initialized.' };
  }

  const { data: sessionData } = await supabase.auth.getSession();
  const user = sessionData?.session?.user;
  
  if (!user) {
    return { success: false, error: 'User must be authenticated to save recording.' };
  }

  const mimeType = audioBlob.type || 'audio/mp4';
  const supportedMimeTypes = ['audio/webm', 'audio/mp4', 'audio/m4a', 'audio/wav', 'audio/mpeg', 'audio/ogg'];
  if (!supportedMimeTypes.includes(mimeType) && !mimeType.startsWith('audio/')) {
    return { success: false, error: 'Unsupported MIME type.' };
  }

  const MAX_FILE_SIZE = 20 * 1024 * 1024;
  if (audioBlob.size > MAX_FILE_SIZE) {
    return { success: false, error: 'File size exceeds 20MB limit.' };
  }

  const uuid = crypto.randomUUID();
  const fileName = `${user.id}/${uuid}.${extension}`;

  // 1. Upload to storage
  const { error: uploadError } = await supabase.storage
    .from('voice-recordings')
    .upload(fileName, audioBlob, { contentType: mimeType });

  if (uploadError) {
    return { success: false, error: `Upload failed: ${uploadError.message}` };
  }

  // 2. Insert metadata
  const { error: insertError } = await supabase.from('voice_recordings').insert({
    user_id: user.id,
    action_card_id: cardId || null,
    storage_path: fileName,
    mime_type: mimeType,
    duration_seconds: durationSeconds,
    consent_for_evaluation: true,
    pipeline: pipeline,
    transcript: transcript
  });

  if (insertError) {
    // Cleanup storage if metadata fails
    await supabase.storage.from('voice-recordings').remove([fileName]);
    return { success: false, error: `Metadata save failed: ${insertError.message}` };
  }

  return { success: true, message: 'Recording saved successfully.', storagePath: fileName };
}

export async function deleteVoiceRecording(storagePath: string): Promise<VoiceRecordingResult> {
  if (!supabase) {
    return { success: false, error: 'Supabase client is not initialized.' };
  }

  const { data: sessionData } = await supabase.auth.getSession();
  const user = sessionData?.session?.user;
  
  if (!user) {
    return { success: false, error: 'User must be authenticated.' };
  }

  // Verify path belongs to user
  if (!storagePath.startsWith(`${user.id}/`)) {
    return { success: false, error: 'Unauthorized path.' };
  }

  const { error: deleteStorageError } = await supabase.storage.from('voice-recordings').remove([storagePath]);
  if (deleteStorageError) {
    return { success: false, error: `Failed to delete audio file: ${deleteStorageError.message}` };
  }

  const { error: deleteMetaError } = await supabase
    .from('voice_recordings')
    .update({ deleted_at: new Date().toISOString() })
    .eq('storage_path', storagePath);
  
  if (deleteMetaError) {
    return { 
      success: false, 
      error: `Partial failure: Audio deleted from storage, but failed to soft-delete metadata: ${deleteMetaError.message}` 
    };
  }

  return { success: true, message: 'Recording deleted successfully.' };
}
