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
  const [confidence, setConfidence] = useState<number | null>(null);
  const [sttProvider, setSttProvider] = useState<string | null>(null);
  const [extractionProvider, setExtractionProvider] = useState<string | null>(null);

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (recordingState === 'captured' && audioChunks.length > 0) {
      const totalSize = audioChunks.reduce((acc, chunk) => acc + chunk.size, 0);
      if (totalSize > 0) {
        handleGenerateActionCard();
      }
    }
  }, [audioChunks, recordingState]);

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
      setAudioChunks([]);

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
    const totalSize = audioChunks.reduce((acc, chunk) => acc + chunk.size, 0);
    if (totalSize === 0) {
      alert('Recording is empty. Please speak into your microphone and try again.');
      return;
    }

    setIsProcessing(true);
    setProcessingStatus('Uploading audio...');

    try {
      const mimeType = mediaRecorder?.mimeType || audioChunks[0]?.type || 'audio/mp4';
      const extension = mimeType.includes('webm') ? 'webm' : 'm4a';
      const audioBlob = new Blob(audioChunks, { type: mimeType });
      const audioFile = new File([audioBlob], `grocery-order.${extension}`, {
        type: mimeType,
      });

      const sttProvider = pipeline.startsWith('sarvam') ? 'sarvam' : 'gemini';
      const extractProvider = pipeline.endsWith('ollama') ? 'ollama' : 'gemini';

      setProcessingStatus('Transcribing recording...');
      const transcription = await transcribeAudio(audioFile, sttProvider);
      setTranscript(transcription.transcript);

      setProcessingStatus('Extracting order details...');

      // Clean up previous generated card in this session if any, to avoid orphaned records
      if (cardId) {
        try {
          await deleteActionCard(cardId);
        } catch (err) {
          console.error("Failed to delete previous action card:", err);
        }
      }

      setProcessingStatus('Generating Action Card...');

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
      setConfidence(card.confidence !== undefined ? card.confidence : null);
      setSttProvider(card.stt_provider || null);
      setExtractionProvider(card.extraction_provider || null);
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
      setConfidence(card.confidence !== undefined ? card.confidence : null);
      setSttProvider(null);
      setExtractionProvider(card.extraction_provider || null);
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
      return "Customer name is missing.";
    }
    const address = deliveryAddress.trim();
    if (!address) {
      return "Delivery address is missing.";
    }
    const validItems = items.filter(i => i.name.trim() !== '');
    if (validItems.length === 0) {
      return "At least one item is required in the order.";
    }
    for (const item of validItems) {
      if (item.quantity <= 0) {
        return `Quantity for "${item.name}" must be greater than 0.`;
      }
      if (item.price !== undefined && item.price !== null && item.price < 0) {
        return `Price for "${item.name}" cannot be negative.`;
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
    <div className={`${isGenerated ? 'space-y-4' : 'space-y-6'} max-w-5xl mx-auto`}>
      {/* Page Header */}
      <div className="text-center flex flex-col items-center justify-center pb-4">
        {isGenerated ? (
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">Review & Confirm Order</h1>
            <p className="text-sm sm:text-base text-slate-500 mt-2 max-w-2xl">
              Verify the AI-extracted details below and submit to register the order.
            </p>
          </div>
        ) : (
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">Voice-to-Order Simulator</h1>
            <p className="mt-2 text-sm sm:text-base text-slate-500 max-w-2xl">
              Simulate the complete phone order workflow: record audio, trigger mock AI parsing, verify details, and register.
            </p>
          </div>
        )}
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
        <div className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Global validation error */}
            {validationError && (
              <div className="text-base text-red-700 font-semibold flex items-center justify-start text-left gap-2 py-0">
                <span className="text-red-500 text-lg shrink-0">⚠</span>
                <span>
                  <span className="font-bold">{validationError}</span>{' '}
                  <span className="text-red-600/90 font-medium">Please edit the order before submission.</span>
                </span>
              </div>
            )}

            {/* Dynamic form warning */}
            {getValidationWarning() && (
              <div className="text-base text-amber-755 font-semibold flex items-center justify-start text-left gap-2 py-0">
                <span className="text-amber-500 text-lg shrink-0">⚠</span>
                <span>
                  <span className="font-bold">{getValidationWarning()}</span>{' '}
                  <span className="text-amber-605 font-medium">Please edit the order before submission.</span>
                </span>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
              {/* Left Column - Forms & Items (Span 2) */}
              <div className="lg:col-span-2 space-y-6">
                {/* Customer & Delivery Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
                  <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      Customer & Delivery Details
                    </h3>
                    {isEditing && (
                      <span className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                        Editing Mode
                      </span>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Customer Name</label>
                          <input
                            type="text"
                            required
                            value={customerName}
                            onChange={(e) => setCustomerName(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-3 py-2 text-sm text-slate-900 transition-colors focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Phone Number</label>
                          <input
                            type="text"
                            required
                            value={customerPhone}
                            onChange={(e) => setCustomerPhone(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-3 py-2 text-sm text-slate-900 transition-colors focus:outline-none"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Delivery Address</label>
                          <input
                            type="text"
                            required
                            value={deliveryAddress}
                            onChange={(e) => setDeliveryAddress(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-3 py-2 text-sm text-slate-900 transition-colors focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Delivery Window</label>
                          <input
                            type="text"
                            required
                            value={deliveryTime}
                            onChange={(e) => setDeliveryTime(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-3 py-2 text-sm text-slate-900 transition-colors focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="space-y-0.5">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Customer</span>
                          <div className="text-sm font-bold text-slate-900 truncate">{customerName || 'N/A'}</div>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Phone Contact</span>
                          <div className="text-xs text-slate-700 font-semibold flex items-center gap-1.5 truncate">
                            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.94.725l.548 2.2a1 1 0 01-.321.988l-1.305.98a10.582 10.582 0 004.872 4.872l.98-1.305a1 1 0 01.988-.321l2.2.548a1 1 0 01.725.94V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                            </svg>
                            <span className="truncate">{customerPhone || 'N/A'}</span>
                          </div>
                        </div>
                        <div className="space-y-0.5 col-span-1">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Delivery Destination</span>
                          <div className="text-xs text-slate-700 font-semibold flex items-start gap-1.5">
                            <svg className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <span className="line-clamp-2 leading-tight">{deliveryAddress || 'N/A'}</span>
                          </div>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Scheduled Time</span>
                          <div className="text-xs text-slate-700 font-semibold flex items-center gap-1.5">
                            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span className="line-clamp-2 leading-tight">{deliveryTime || 'N/A'}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Line Items Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
                  <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 002-2h-2" />
                      </svg>
                      Extracted Order Items
                    </h3>
                    {isEditing && (
                      <button
                        type="button"
                        onClick={addEditItemRow}
                        className="text-xs font-bold text-indigo-600 hover:text-indigo-805 transition-colors cursor-pointer flex items-center gap-1"
                      >
                        <span>+ Add Row</span>
                      </button>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="space-y-3">
                      {items.map((item, idx) => (
                        <div key={idx} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pb-2 sm:pb-0 border-b sm:border-b-0 border-slate-100 last:border-b-0">
                          <input
                            type="text"
                            required
                            placeholder="Item Name"
                            value={item.name}
                            onChange={(e) => handleItemChange(idx, 'name', e.target.value)}
                            className="flex-1 bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-3 py-1.5 text-sm text-slate-900 focus:outline-none transition-colors"
                          />
                          <div className="flex gap-2">
                            <input
                              type="number"
                              min="0.01"
                              step="0.01"
                              placeholder="Qty"
                              value={item.quantity}
                              onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                              className="w-16 bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-2 py-1.5 text-sm text-slate-900 focus:outline-none text-center transition-colors"
                            />
                            <input
                              type="text"
                              placeholder="Unit"
                              value={item.unit || ""}
                              onChange={(e) => handleItemChange(idx, "unit", e.target.value)}
                              className="w-20 bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-2 py-1.5 text-sm text-slate-900 focus:outline-none transition-colors"
                            />
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              placeholder="Price"
                              value={item.price || ''}
                              onChange={(e) => handleItemChange(idx, 'price', e.target.value)}
                              className="w-24 bg-slate-50 border border-slate-200 hover:border-slate-350 focus:border-indigo-500 focus:bg-white rounded-lg px-2 py-1.5 text-sm text-slate-900 focus:outline-none text-right font-mono transition-colors"
                            />
                            <button
                              type="button"
                              onClick={() => removeEditItemRow(idx)}
                              disabled={items.length === 1}
                              className="text-slate-400 hover:text-red-650 disabled:opacity-35 cursor-pointer font-bold text-lg px-2"
                            >
                              &times;
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="overflow-hidden border border-slate-100 rounded-lg">
                      <table className="min-w-full divide-y divide-slate-100 text-left text-xs sm:text-sm">
                        <thead className="bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                          <tr>
                            <th className="py-2.5 px-4">Item Name</th>
                            <th className="py-2.5 px-4 text-center w-24">Qty / Unit</th>
                            <th className="py-2.5 px-4 text-right w-28">Est. Price</th>
                            <th className="py-2.5 px-4 text-right w-28">Total Price</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {items.map((item, idx) => {
                            const hasPrice = item.price !== undefined && item.price !== null && item.price > 0;
                            const itemTotal = hasPrice ? item.quantity * (item.price || 0) : 0;
                            return (
                              <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                                <td className="py-3 px-4 font-semibold text-slate-800">{item.name || 'Unnamed Item'}</td>
                                <td className="py-3 px-4 text-center text-slate-650 font-medium">
                                  {item.quantity} {item.unit || ''}
                                </td>
                                <td className="py-3 px-4 text-right font-mono font-medium text-slate-600">
                                  {hasPrice ? `₹${(item.price || 0).toFixed(2)}` : <span className="text-[11px] text-slate-400 italic font-sans">Pending</span>}
                                </td>
                                <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                                  {hasPrice ? `₹${itemTotal.toFixed(2)}` : <span className="text-[11px] text-slate-400 italic font-sans">-</span>}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="mt-4 pt-4 border-t border-slate-100 flex justify-between items-center text-sm font-semibold text-slate-600">
                    <span className="text-slate-500">Calculated Grand Total:</span>
                    {items.some(item => item.price === undefined || item.price === null || item.price <= 0) ? (
                      <span className="text-amber-600 font-bold text-xs italic bg-amber-50 px-2 py-1 rounded border border-amber-200">
                        Pending Price Verification
                      </span>
                    ) : (
                      <span className="text-base sm:text-lg font-black text-slate-900 font-mono bg-slate-50 border border-slate-150 px-3 py-1 rounded">
                        ₹{orderTotal.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column - Status, Signals & Transcript (Span 1) */}
              <div className="space-y-6">


                {/* Transcript Card */}
                {transcript && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                    <h3 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 flex items-center gap-2">
                      <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      </svg>
                      Speech Transcript
                    </h3>
                    <p className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-150 italic leading-relaxed font-medium">
                      "{transcript}"
                    </p>
                  </div>
                )}

                {/* Audio Actions Evaluation Panel */}
                {orderSource === 'audio' && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                    <h3 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 flex items-center gap-2">
                      <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      Evaluation & QA
                    </h3>
                    {!audioSaved ? (
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
                              true,
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
                        className="w-full px-3 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 rounded-lg text-xs font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        {isSavingAudio ? 'Saving...' : '💾 Save Audio for AI Eval'}
                      </button>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-750">
                          <span className="text-emerald-600 font-extrabold text-sm">✓</span>
                          <span>Recording Available</span>
                        </div>
                        <button
                          type="button"
                          disabled={isSavingAudio}
                          onClick={async () => {
                            setIsSavingAudio(true);
                            try {
                              const { deleteVoiceRecording } = await import('@/lib/voice-recordings');
                              const res = await deleteVoiceRecording(audioStoragePath!);
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
                          className="w-full px-3 py-2 bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 rounded-lg text-xs font-bold transition-colors cursor-pointer text-center"
                        >
                          Delete Recording
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>



            {/* Actions Footer Bar */}
            <div className="pt-4 border-t border-slate-200 flex justify-between items-center gap-3">
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
                className="px-4 py-2 border border-slate-255 hover:bg-slate-50 rounded-lg text-xs font-bold text-slate-650 hover:text-slate-900 transition-colors cursor-pointer"
              >
                Cancel Order
              </button>

              <div className="flex items-center gap-2">
                {!isEditing ? (
                  <button
                    type="button"
                    onClick={() => setIsEditing(true)}
                    className="px-4 py-2 bg-slate-50 hover:bg-slate-105 border border-slate-255 rounded-lg text-xs font-bold text-slate-700 transition-colors cursor-pointer"
                  >
                    Edit Details
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                  >
                    Finish Editing
                  </button>
                )}

                <button
                  type="submit"
                  disabled={!!getValidationWarning()}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-305 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold rounded-lg transition-all shadow-xs cursor-pointer"
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
