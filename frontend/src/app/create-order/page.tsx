'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { createActionCard, extractActionCard, transcribeAudio, updateActionCard, deleteActionCard } from '@/lib/api';
import { saveVoiceRecording } from '@/lib/voice-recordings';
import { Item } from '@/types';

export default function CreateOrder() {
  const router = useRouter();

  // Audio Recorder States
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [recordingState, setRecordingState] = useState<'idle' | 'recording' | 'captured'>('idle');
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  // Workflow States
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [isGenerated, setIsGenerated] = useState(false);
  const [cardId, setCardId] = useState<string | null>(null);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [isQuotaError, setIsQuotaError] = useState(false);
  const [manualTranscript, setManualTranscript] = useState('');
  const [orderSource, setOrderSource] = useState<'audio' | 'text'>('audio');
  const [pipeline, setPipeline] = useState('gemini_gemini');
  const [audioSaved, setAudioSaved] = useState(false);
  const [audioStoragePath, setAudioStoragePath] = useState<string | null>(null);
  const [isSavingAudio, setIsSavingAudio] = useState(false);
  // Generated Card Editing States
  const [isEditing, setIsEditing] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [deliveryTime, setDeliveryTime] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [transcript, setTranscript] = useState('');

  // Risk and Validation States
  const [riskFlags, setRiskFlags] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [paymentMethod, setPaymentMethod] = useState<string>('Not Specified');

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // MediaRecorder Start
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredMimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/mp4')
          ? 'audio/mp4'
          : '';

      const recorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream);
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunks.push(e.data);
        }
      };

      recorder.onstop = () => {
        const actualMimeType = recorder.mimeType || chunks[0]?.type || 'audio/mp4';
        const audioBlob = new Blob(chunks, { type: actualMimeType });
        const url = URL.createObjectURL(audioBlob);
        setAudioUrl(url);
        setAudioChunks(chunks);
        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setMediaRecorder(recorder);
      setRecordingState('recording');
      setRecordingSeconds(0);
      setAudioUrl(null);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      alert("Error: Microphone access is required to capture audio.");
      console.error(err);
    }
  };

  // MediaRecorder Stop
  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setRecordingState('captured');
    }
  };

  const discardRecording = () => {
    setAudioUrl(null);
    setAudioChunks([]);
    setRecordingState('idle');
    setAudioSaved(false);
    setAudioStoragePath(null);
  };

  const handleGenerateActionCard = async () => {
    if (audioChunks.length === 0) {
      alert('Please record an order before generating an Action Card.');
      return;
    }

    setIsProcessing(true);
    setProcessingStatus('Transcribing speech logs...');

    try {
      const mimeType = mediaRecorder?.mimeType || audioChunks[0]?.type || 'audio/mp4';
      const extension = mimeType.includes('webm') ? 'webm' : 'm4a';
      const audioBlob = new Blob(audioChunks, { type: mimeType });
      const audioFile = new File([audioBlob], `grocery-order.${extension}`, {
        type: mimeType,
      });

      const sttProvider = pipeline.startsWith('sarvam') ? 'sarvam' : 'gemini';
      const extractProvider = pipeline.endsWith('ollama') ? 'ollama' : 'gemini';

      const transcription = await transcribeAudio(audioFile, sttProvider);
      setTranscript(transcription.transcript);

      setProcessingStatus(`Running ${extractProvider === 'ollama' ? 'Ollama' : 'Gemini AI'} structured entity extraction...`);

      // Clean up previous generated card in this session if any, to avoid orphaned records
      if (cardId) {
        try {
          await deleteActionCard(cardId);
        } catch (err) {
          console.error("Failed to delete previous action card:", err);
        }
      }

      const card = await extractActionCard(transcription.transcript, 'audio', extractProvider, sttProvider, pipeline, true);
      setCardId(card.id);
      setOrderSource('audio');
      setAudioSaved(false);
      setAudioStoragePath(null);

      setCustomerName(card.customer_name || '');
      setCustomerPhone(card.customer_phone || '');
      setDeliveryAddress(card.delivery_address || '');
      setDeliveryTime(card.delivery_time || '');
      setItems(card.items || []);
      setRiskFlags(card.risk_flags || []);
      setValidationWarnings(card.validation_warnings || []);
      setPaymentMethod(card.payment_method || 'Not Specified');
      setIsGenerated(true);
      setIsEditing(false);
      setExtractionError(null);
      setIsQuotaError(false);
    } catch (error) {
      console.error(error);
      const errMsg = error instanceof Error ? error.message : String(error);
      const isQuota = errMsg.includes('429') ||
                      errMsg.toUpperCase().includes('RESOURCE_EXHAUSTED') ||
                      errMsg.toUpperCase().includes('QUOTA') ||
                      errMsg.toUpperCase().includes('RATE_LIMIT') ||
                      errMsg.includes('temporarily unavailable');

      if (isQuota) {
        setIsQuotaError(true);
        setExtractionError(null);
      } else {
        setExtractionError('Could not extract order. Please retry recording.');
      }
      setIsGenerated(false);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleGenerateActionCardFromText = async () => {
    if (!manualTranscript.trim()) {
      alert('Please enter the order details/transcript.');
      return;
    }

    setIsProcessing(true);
    setProcessingStatus('Running structured entity extraction...');

    try {
      // Clean up previous generated card in this session if any
      if (cardId) {
        try {
          await deleteActionCard(cardId);
        } catch (err) {
          console.error("Failed to delete previous action card:", err);
        }
      }

      const extractProvider = pipeline.endsWith('ollama') ? 'ollama' : 'gemini';
      const sttProvider = pipeline.startsWith('sarvam') ? 'sarvam' : 'gemini';
      const card = await extractActionCard(manualTranscript, 'text', extractProvider, sttProvider, pipeline, true);
      setCardId(card.id);
      setOrderSource('text');

      setCustomerName(card.customer_name || '');
      setCustomerPhone(card.customer_phone || '');
      setDeliveryAddress(card.delivery_address || '');
      setDeliveryTime(card.delivery_time || '');
      setItems(card.items || []);
      setRiskFlags(card.risk_flags || []);
      setValidationWarnings(card.validation_warnings || []);
      setPaymentMethod(card.payment_method || 'Not Specified');
      setTranscript(manualTranscript);
      setIsGenerated(true);
      setIsEditing(false);
      setExtractionError(null);
      setIsQuotaError(false);
    } catch (error) {
      console.error(error);
      const errMsg = error instanceof Error ? error.message : String(error);
      const isQuota = errMsg.includes('429') ||
                      errMsg.toUpperCase().includes('RESOURCE_EXHAUSTED') ||
                      errMsg.toUpperCase().includes('QUOTA') ||
                      errMsg.toUpperCase().includes('RATE_LIMIT') ||
                      errMsg.includes('temporarily unavailable');

      if (isQuota) {
        setExtractionError('Voice processing is temporarily unavailable due to API quota limits. Please enter the order manually.');
        setIsQuotaError(true);
      } else {
        setExtractionError('Could not extract order details. Please verify your text and try again.');
      }
      setIsGenerated(false);
    } finally {
      setIsProcessing(false);
    }
  };

  // Inline Item Changes
  const handleItemChange = (index: number, field: keyof Item, value: any) => {
    const updated = [...items];
    if (field === 'quantity') {
      (updated[index] as any)[field] = Math.max(0.01, parseFloat(value) || 1);
    } else if (field === 'price') {
      (updated[index] as any)[field] = Math.max(0, parseFloat(value) || 0);
    } else {
      (updated[index] as any)[field] = value;
    }
    setItems(updated);
  };

  const addEditItemRow = () => {
    setItems([...items, { name: '', quantity: 1, price: 0 }]);
  };

  const removeEditItemRow = (index: number) => {
    if (items.length > 1) {
      setItems(items.filter((_, idx) => idx !== index));
    }
  };

  // Calculate order sum total
  const orderTotal = items.reduce((sum, item) => sum + (item.quantity * (item.price || 0)), 0);

  const [validationError, setValidationError] = useState<string | null>(null);

  // Dynamic validation check for rendering warnings
  const getValidationWarning = () => {
    const name = customerName.trim();
    if (!name || name.toLowerCase() === 'unknown') {
      return "Customer Name is required and cannot be 'Unknown'.";
    }
    const address = deliveryAddress.trim();
    if (!address) {
      return "Delivery Address is required.";
    }
    const validItems = items.filter(i => i.name.trim() !== '');
    if (validItems.length === 0) {
      return "At least one valid item name is required.";
    }
    for (const item of validItems) {
      if (item.quantity <= 0) {
        return `Item "${item.name}" must have a valid quantity greater than 0.`;
      }
      if (item.price !== undefined && item.price !== null && item.price < 0) {
        return `Item "${item.name}" cannot have a negative price.`;
      }
    }
    return null;
  };

  // Submit to Database/LocalStorage
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const warning = getValidationWarning();
    if (warning) {
      setValidationError(warning);
      return;
    }

    setValidationError(null);
    setIsProcessing(true);
    setProcessingStatus('Saving order card...');

    const validItems = items.filter(i => i.name.trim() !== '');

    const payload = {
      customer_name: customerName,
      customer_phone: customerPhone,
      delivery_address: deliveryAddress,
      delivery_time: deliveryTime,
      items: validItems,
      status: 'pending',
      source: orderSource,
      transcript: transcript
    };

    try {
      if (cardId) {
        await updateActionCard(cardId, payload);
      } else {
        await createActionCard(payload);
      }
      router.push('/orders');
      router.refresh();
    } catch (err) {
      alert("Failed to submit order. Falling back to local storage.");
      setIsProcessing(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Voice-to-Order Simulator</h1>
        <p className="mt-1 text-sm text-slate-500">
          Simulate the complete phone order workflow: record audio, trigger mock AI parsing, verify details, and register.
        </p>
      </div>

      {/* Voice Recording Control Panel */}
      {!isGenerated && !isProcessing && !extractionError && !isQuotaError && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 space-y-6 shadow-sm text-center">
          <h2 className="text-lg font-bold text-slate-900">Capture Phone Call Order</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Record customer voice logs live. Click start, dictate the order, stop, and process the results.
          </p>

          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="w-full max-w-xs text-left mb-2">
              <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">AI Pipeline</label>
              <select
                value={pipeline}
                onChange={(e) => setPipeline(e.target.value)}
                disabled={recordingState === 'recording' || isProcessing}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
              >
                <option value="gemini_gemini">Gemini STT + Gemini Extraction</option>
                <option value="sarvam_gemini">Sarvam STT + Gemini Extraction</option>
                <option value="sarvam_ollama">Sarvam STT + Ollama Extraction (Qwen 2.5)</option>
              </select>
            </div>

            {recordingState === 'recording' && (
              <div className="flex items-center space-x-2 bg-red-50 text-red-700 px-4 py-2 rounded-lg border border-red-200">
                <span className="h-2 w-2 rounded-full bg-red-600 animate-pulse"></span>
                <span className="text-xs font-bold uppercase tracking-wider">RECORDING ({formatTime(recordingSeconds)})</span>
              </div>
            )}

            {recordingState === 'captured' && audioUrl && (
              <div className="space-y-3">
                <div className="bg-indigo-50 text-indigo-805 px-4 py-2 rounded-lg border border-indigo-100 text-xs font-semibold">
                  Audio Captured Successfully
                </div>
                <audio src={audioUrl} controls className="mx-auto" />
              </div>
            )}

            <div className="flex items-center gap-3 pt-2">
              {recordingState !== 'recording' ? (
                <button
                  type="button"
                  onClick={startRecording}
                  className="px-5 py-3 bg-indigo-600 hover:bg-indigo-705 text-white font-bold rounded-lg text-sm transition-colors cursor-pointer shadow-sm"
                >
                  Start Recording
                </button>
              ) : (
                <button
                  type="button"
                  onClick={stopRecording}
                  className="px-5 py-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-lg text-sm transition-colors cursor-pointer shadow-sm"
                >
                  Stop Recording
                </button>
              )}

              {recordingState === 'captured' && (
                <div className="flex flex-col items-center gap-3 mt-2">
                  <button
                    type="button"
                    onClick={handleGenerateActionCard}
                    className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-sm transition-colors cursor-pointer shadow-sm w-full max-w-xs"
                  >
                    Generate Action Card
                  </button>
                  <button
                    type="button"
                    onClick={discardRecording}
                    className="px-5 py-2 text-slate-500 hover:text-slate-700 text-xs font-bold transition-colors cursor-pointer"
                  >
                    Discard Recording
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Explicit Error State Panel */}
      {extractionError && !isProcessing && !isQuotaError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center shadow-sm space-y-6">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-650">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-bold text-red-950">Could not extract order</h3>
            <p className="text-xs text-red-700 font-medium">
              We couldn't process the audio or extract order details. Please check if your audio is clear and try again.
            </p>
          </div>
          <div>
            <button
              type="button"
              onClick={() => {
                setExtractionError(null);
                setRecordingState('idle');
                setAudioUrl(null);
                setAudioChunks([]);
                setRecordingSeconds(0);
              }}
              className="px-5 py-2.5 bg-red-650 hover:bg-red-750 text-white font-bold rounded-lg text-sm transition-colors shadow-sm cursor-pointer"
            >
              Retry Recording
            </button>
          </div>
        </div>
      )}

      {/* Quota Error / Manual Fallback Panel */}
      {isQuotaError && !isProcessing && (
        <div className="rounded-xl border border-amber-250 bg-amber-50 p-8 shadow-sm space-y-6">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-705">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>

          <div className="space-y-2 text-center">
            <h3 className="text-lg font-bold text-amber-950">Voice Processing Unavailable</h3>
            <p className="text-sm text-amber-805 font-semibold max-w-md mx-auto">
              Voice processing is temporarily unavailable due to API quota limits. Please enter the order manually.
            </p>
          </div>

          <div className="max-w-xl mx-auto space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-2">
                Order Transcript / Details
              </label>
              <textarea
                value={manualTranscript}
                onChange={(e) => setManualTranscript(e.target.value)}
                placeholder="Example: Johnathan Archer, +1 310-555-2150. Deliver 2 units of Plasma Injector Model D to Starbase 1 ASAP."
                rows={4}
                className="w-full bg-white border border-slate-350 rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              />
            </div>

            <div className="flex justify-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setIsQuotaError(false);
                  setExtractionError(null);
                  setRecordingState('idle');
                  setAudioUrl(null);
                  setAudioChunks([]);
                  setRecordingSeconds(0);
                }}
                className="px-5 py-2.5 border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-bold rounded-lg text-sm transition-colors cursor-pointer"
              >
                Back to Voice
              </button>

              <button
                type="button"
                onClick={handleGenerateActionCardFromText}
                disabled={!manualTranscript.trim()}
                className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 disabled:cursor-not-allowed text-white font-bold rounded-lg text-sm transition-colors shadow-sm cursor-pointer"
              >
                Generate Action Card
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Simulated Processing Loader */}
      {isProcessing && (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm space-y-4">
          <div className="h-8 w-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <h3 className="text-lg font-bold text-slate-900">Transcribing and generating Action Card...</h3>
          <p className="text-xs text-slate-500 font-semibold">{processingStatus}</p>
        </div>
      )}

      {/* Action Card Verification Panel */}
      {isGenerated && !isProcessing && (
        <div className="space-y-6">
          <div className="bg-indigo-50 border border-indigo-150 p-4 rounded-xl text-xs text-indigo-800 leading-relaxed font-semibold">
            <span className="font-extrabold uppercase mr-1">[Mock Speech Result]</span>
            A transcript has been processed and entities mapped. Please review details below before submitting.
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h2 className="text-lg font-bold text-slate-900">Verify Action Card Details</h2>
                <span className="text-xs bg-amber-50 text-amber-705 border border-amber-250 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                  Pending Review
                </span>
              </div>

              {isEditing ? (
                /* Editable Form Mode */
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Customer Name</label>
                      <input
                        type="text"
                        required
                        value={customerName}
                        onChange={(e) => setCustomerName(e.target.value)}
                        className="w-full bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm text-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Phone Number</label>
                      <input
                        type="text"
                        required
                        value={customerPhone}
                        onChange={(e) => setCustomerPhone(e.target.value)}
                        className="w-full bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm text-slate-900"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Delivery Address</label>
                      <input
                        type="text"
                        required
                        value={deliveryAddress}
                        onChange={(e) => setDeliveryAddress(e.target.value)}
                        className="w-full bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm text-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Requested Time</label>
                      <input
                        type="text"
                        required
                        value={deliveryTime}
                        onChange={(e) => setDeliveryTime(e.target.value)}
                        className="w-full bg-white border border-slate-300 rounded-lg px-4 py-2 text-sm text-slate-900"
                      />
                    </div>
                  </div>

                  {/* Line Items Editor */}
                  <div className="pt-4 border-t border-slate-100">
                    <div className="flex justify-between items-center mb-3">
                      <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Line Items</h3>
                      <button
                        type="button"
                        onClick={addEditItemRow}
                        className="text-xs font-bold text-indigo-650 hover:text-indigo-800 cursor-pointer"
                      >
                        + Add Item Row
                      </button>
                    </div>
                    <div className="space-y-3">
                      {items.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-3">
                          <input
                            type="text"
                            required
                            placeholder="Item Name"
                            value={item.name}
                            onChange={(e) => handleItemChange(idx, 'name', e.target.value)}
                            className="flex-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900"
                          />
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            placeholder="Qty"
                            value={item.quantity}
                            onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                            className="w-20 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 text-center"
                          />
                          <input
                            type="text"
                            placeholder="Unit"
                            value={item.unit || ""}
                            onChange={(e) => handleItemChange(idx, "unit", e.target.value)}
                            className="w-24 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900"
                          />
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            placeholder="Price"
                            value={item.price || ''}
                            onChange={(e) => handleItemChange(idx, 'price', e.target.value)}
                            className="w-24 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 text-right font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => removeEditItemRow(idx)}
                            disabled={items.length === 1}
                            className="text-slate-400 hover:text-red-650 disabled:opacity-35 cursor-pointer font-bold text-lg"
                          >
                            &times;
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={() => setIsEditing(false)}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-705 text-white font-bold rounded-lg text-xs cursor-pointer"
                    >
                      Done Editing
                    </button>
                  </div>
                </div>
              ) : (
                /* Static Review Mode */
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Customer Details</h4>
                      <p className="text-sm font-bold text-slate-900 mt-1">{customerName}</p>
                      <p className="text-xs text-slate-500 mt-0.5">Phone: {customerPhone}</p>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Delivery Details</h4>
                      <p className="text-sm font-bold text-slate-900 mt-1">{deliveryAddress}</p>
                      <p className="text-xs text-slate-500 mt-0.5 font-medium">Requested Window: {deliveryTime}</p>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-100">
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Payment Details</h4>
                    <p className={`text-xs mt-1 font-bold ${
                      paymentMethod === 'Credit (Udhaar)' ? 'text-red-650' :
                      paymentMethod === 'Cash' || paymentMethod === 'Online' ? 'text-emerald-650' :
                      'text-slate-600'
                    }`}>
                      {paymentMethod}
                    </p>
                  </div>

                  <div className="pt-4 border-t border-slate-100">
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Extracted Order Line Items</h4>
                    <div className="space-y-1.5">
                      {items.map((item, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs p-2 rounded bg-slate-50 border border-slate-100">
                          <div className="text-slate-800 font-medium">
                            <span className="font-bold text-slate-900">
                              {item.quantity}
                              {item.unit ? ` ${item.unit}` : ""}
                            </span>{" "}
                            {item.name}
                          </div>
                          {item.price !== undefined && item.price !== null && item.price > 0 ? (
                            <div className="text-right font-mono text-slate-550 font-bold">
                              ₹{(item.price * item.quantity).toFixed(2)}
                            </div>
                          ) : (
                            <div className="text-right text-slate-400 font-medium italic text-[11px]">
                              Price not available
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-100 space-y-2">
                    {riskFlags.length > 0 && (
                      <div className="bg-red-50 border border-red-200 p-3 rounded-lg text-[10px] text-red-800 font-semibold leading-relaxed flex items-start gap-2 my-2">
                        <svg className="h-4 w-4 text-red-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <div>
                          <span className="font-extrabold uppercase mr-1">Risk Detected:</span>
                          {riskFlags.join(", ")}
                        </div>
                      </div>
                    )}

                    {validationWarnings.length > 0 && (
                      <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg text-[10px] text-slate-700 font-semibold leading-relaxed flex items-start gap-2 my-2">
                        <svg className="h-4 w-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <div>
                          <span className="font-extrabold uppercase mr-1">Validation Warnings:</span>
                          {validationWarnings.join(" ")}
                        </div>
                      </div>
                    )}
                  </div>

                  {transcript && (
                    <div className="pt-4 border-t border-slate-100">
                      <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Processed Speech Transcript</h4>
                      <blockquote className="mt-2 text-xs text-slate-650 bg-slate-50 p-3 rounded border border-slate-150 italic leading-relaxed font-medium">
                        "{transcript}"
                      </blockquote>
                    </div>
                  )}
                </div>
              )}

              <div className="pt-4 border-t border-slate-100 flex justify-between items-center text-sm font-semibold text-slate-500">
                <span>Calculated Total:</span>
                {items.some(item => item.price === undefined || item.price === null || item.price <= 0) ? (
                  <span className="text-amber-600 font-bold text-xs italic">Pending Price Verification</span>
                ) : (
                  <span className="text-lg font-extrabold text-slate-900 font-mono">₹{orderTotal.toFixed(2)}</span>
                )}
              </div>
            </div>

            {getValidationWarning() && (
              <div className="bg-amber-50 border border-amber-250 p-4 rounded-xl text-xs text-amber-805 font-semibold leading-relaxed flex items-start gap-2.5 my-4">
                <svg className="h-5 w-5 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div>
                  <span className="font-extrabold uppercase mr-1">[Validation Warning]</span>
                  {getValidationWarning()} Please edit the card details to complete the order fields before submitting.
                </div>
              </div>
            )}

            {/* Verification Footer Action Controls */}
            <div className="flex justify-between items-center mt-4">
              <div className="flex items-center">
                {orderSource === 'audio' && !audioSaved && (
                  <button
                    type="button"
                    disabled={isSavingAudio}
                    onClick={async () => {
                      if (!cardId) return;
                      setIsSavingAudio(true);
                      try {
                        const mimeType = mediaRecorder?.mimeType || audioChunks[0]?.type || 'audio/mp4';
                        const extension = mimeType.includes('webm') ? 'webm' : 'm4a';
                        const audioBlob = new Blob(audioChunks, { type: mimeType });

                        const res = await saveVoiceRecording(
                          audioBlob,
                          extension,
                          recordingSeconds,
                          cardId,
                          true, // Explicit consent granted by clicking this button
                          pipeline,
                          transcript
                        );
                        if (res.success && res.storagePath) {
                          setAudioSaved(true);
                          setAudioStoragePath(res.storagePath);
                          alert('Audio saved successfully for evaluation!');
                        } else {
                          alert(`Failed to save audio: ${res.error}`);
                        }
                      } finally {
                        setIsSavingAudio(false);
                      }
                    }}
                    className="px-4 py-2.5 bg-indigo-50 text-indigo-600 border border-indigo-200 rounded-lg text-xs font-bold hover:bg-indigo-100 transition-colors disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                  >
                    {isSavingAudio ? 'Saving...' : '💾 Save Audio for AI Eval'}
                  </button>
                )}
                {audioSaved && audioStoragePath && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-2 rounded border border-emerald-200">
                      Audio Saved ✔
                    </span>
                    <button
                      type="button"
                      disabled={isSavingAudio}
                      onClick={async () => {
                        setIsSavingAudio(true);
                        try {
                          const { deleteVoiceRecording } = await import('@/lib/voice-recordings');
                          const res = await deleteVoiceRecording(audioStoragePath);
                          if (res.success) {
                            setAudioSaved(false);
                            setAudioStoragePath(null);
                            alert('Recording deleted.');
                          } else {
                            alert(`Failed to delete recording: ${res.error}`);
                          }
                        } finally {
                          setIsSavingAudio(false);
                        }
                      }}
                      className="px-2 py-2 text-xs font-bold text-red-600 hover:text-red-800 cursor-pointer"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={async () => {
                    if (cardId) {
                      try {
                        await deleteActionCard(cardId);
                      } catch (err) {
                        console.error("Failed to delete cancelled card:", err);
                      }
                      setCardId(null);
                    }
                    setIsGenerated(false);
                    setRecordingState('idle');
                    setAudioUrl(null);
                  }}
                  className="px-4 py-2.5 border border-slate-300 rounded-lg text-sm font-bold text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                {!isEditing && (
                  <button
                    type="button"
                    onClick={() => setIsEditing(true)}
                    className="px-4 py-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-sm font-bold text-slate-700 transition-colors cursor-pointer"
                  >
                    Edit Card
                  </button>
                )}

                <button
                  type="submit"
                  disabled={!!getValidationWarning()}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-705 disabled:bg-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-lg text-sm transition-colors shadow-sm cursor-pointer"
                >
                  Submit Order
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
