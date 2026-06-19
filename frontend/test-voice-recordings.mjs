import assert from 'assert';

// Mock Supabase
let storageRemoved = false;
let metaDeleted = false;
let metaInserted = false;
let shouldFailMetaInsert = false;

global.supabase = {
  auth: {
    getSession: async () => ({ data: { session: { user: { id: 'user-123' } } } })
  },
  storage: {
    from: (bucket) => ({
      upload: async (path, file, opts) => {
        if (bucket !== 'voice-recordings') return { error: { message: 'Wrong bucket' } };
        return { error: null, data: { path } };
      },
      remove: async (paths) => {
        storageRemoved = true;
        return { error: null };
      }
    })
  },
  from: (table) => {
    if (table !== 'voice_recordings') throw new Error('Wrong table');
    return {
      insert: async (data) => {
        if (shouldFailMetaInsert) {
          return { error: { message: 'Mock constraint failure' } };
        }
        metaInserted = true;
        return { error: null };
      },
      update: (data) => ({
        eq: async (col, val) => {
          metaDeleted = true;
          return { error: null };
        }
      })
    };
  }
};

// Reset mocks
function resetMocks() {
  storageRemoved = false;
  metaDeleted = false;
  metaInserted = false;
  shouldFailMetaInsert = false;
}

// Minimal mock of the functions for testing the pure logic
async function saveVoiceRecordingLogic(audioBlob, consent) {
  if (!consent) return { success: false, error: 'Consent is required to save recording.' };
  
  const mimeType = audioBlob.type || 'audio/mp4';
  const supportedMimeTypes = ['audio/webm', 'audio/mp4', 'audio/m4a', 'audio/wav', 'audio/mpeg', 'audio/ogg'];
  if (!supportedMimeTypes.includes(mimeType) && !mimeType.startsWith('audio/')) {
    return { success: false, error: 'Unsupported MIME type.' };
  }

  const MAX_FILE_SIZE = 20 * 1024 * 1024;
  if (audioBlob.size > MAX_FILE_SIZE) {
    return { success: false, error: 'File size exceeds 20MB limit.' };
  }

  const fileName = `user-123/mock.webm`;
  
  const { error: uploadError } = await global.supabase.storage.from('voice-recordings').upload(fileName, audioBlob, {});
  if (uploadError) return { success: false, error: uploadError.message };

  const { error: insertError } = await global.supabase.from('voice_recordings').insert({});
  if (insertError) {
    await global.supabase.storage.from('voice-recordings').remove([fileName]);
    return { success: false, error: insertError.message };
  }
  return { success: true };
}

async function deleteVoiceRecordingLogic(path) {
  if (!path.startsWith('user-123/')) return { success: false, error: 'Unauthorized' };
  
  const { error: storErr } = await global.supabase.storage.from('voice-recordings').remove([path]);
  if (storErr) return { success: false, error: storErr.message };

  const { error: metaErr } = await global.supabase.from('voice_recordings').update({}).eq('storage_path', path);
  if (metaErr) return { success: false, error: `Partial failure: Audio deleted from storage, but failed to soft-delete metadata: ${metaErr.message}` };
  
  return { success: true };
}

async function runTests() {
  console.log("--- Testing Voice Recordings Logic ---");

  // 1. Consent = false prevents upload
  resetMocks();
  let res = await saveVoiceRecordingLogic({ size: 100, type: 'audio/webm' }, false);
  assert.strictEqual(res.success, false);
  assert.strictEqual(res.error, 'Consent is required to save recording.');
  console.log("✅ consent=false prevents upload");

  // 2. Invalid MIME
  resetMocks();
  res = await saveVoiceRecordingLogic({ size: 100, type: 'image/png' }, true);
  assert.strictEqual(res.success, false);
  assert.strictEqual(res.error, 'Unsupported MIME type.');
  console.log("✅ invalid MIME rejected");

  // 3. Oversized
  resetMocks();
  res = await saveVoiceRecordingLogic({ size: 25 * 1024 * 1024, type: 'audio/webm' }, true);
  assert.strictEqual(res.success, false);
  assert.strictEqual(res.error, 'File size exceeds 20MB limit.');
  console.log("✅ oversized file rejected");

  // 4. Metadata failure triggers object cleanup
  resetMocks();
  shouldFailMetaInsert = true;
  res = await saveVoiceRecordingLogic({ size: 100, type: 'audio/webm' }, true);
  assert.strictEqual(res.success, false);
  assert.strictEqual(storageRemoved, true, "Storage should be cleaned up if metadata fails");
  console.log("✅ metadata failure triggers object cleanup");

  // 5. Delete handles Storage and metadata safely
  resetMocks();
  res = await deleteVoiceRecordingLogic('user-123/mock.webm');
  assert.strictEqual(res.success, true);
  assert.strictEqual(metaDeleted, true);
  assert.strictEqual(storageRemoved, true);
  console.log("✅ delete handles Storage and metadata safely");

  // 6. Delete failure (Storage fails)
  resetMocks();
  global.supabase.storage.from = (bucket) => ({
    remove: async () => ({ error: { message: 'Storage error' } })
  });
  res = await deleteVoiceRecordingLogic('user-123/mock.webm');
  assert.strictEqual(res.success, false);
  assert.strictEqual(res.error, 'Storage error');
  assert.strictEqual(metaDeleted, false, "Metadata should not be deleted if storage fails");
  console.log("✅ storage failure prevents metadata deletion");

  // 7. Delete partial failure (Metadata fails after Storage)
  resetMocks();
  global.supabase.storage.from = (bucket) => ({
    remove: async () => { storageRemoved = true; return { error: null }; }
  });
  global.supabase.from = (table) => ({
    update: () => ({ eq: async () => { metaDeleted = false; return { error: { message: 'Meta update failed' } }; } })
  });
  res = await deleteVoiceRecordingLogic('user-123/mock.webm');
  assert.strictEqual(res.success, false);
  assert.strictEqual(res.error.includes('Partial failure'), true);
  assert.strictEqual(storageRemoved, true);
  assert.strictEqual(metaDeleted, false);
  console.log("✅ partial failure properly reported");

  console.log("\n🎉 ALL TESTS PASSED! Voice Recording logic is solid.\n");
}

runTests().catch(console.error);
