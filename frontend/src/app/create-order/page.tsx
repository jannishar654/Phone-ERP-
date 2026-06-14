'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { createActionCard, extractActionCard, transcribeAudio, updateActionCard, deleteActionCard } from '@/lib/api';
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
  
  // Generated Card Editing States
  const [isEditing, setIsEditing] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [deliveryTime, setDeliveryTime] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [transcript, setTranscript] = useState('');

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

      const transcription = await transcribeAudio(audioFile);
      setTranscript(transcription.transcript);

      setProcessingStatus('Running Gemini AI structured entity extraction...');
      
      // Clean up previous generated card in this session if any, to avoid orphaned records
      if (cardId) {
        try {
          await deleteActionCard(cardId);
        } catch (err) {
          console.error("Failed to delete previous action card:", err);
        }
      }

      const card = await extractActionCard(transcription.transcript, 'audio');
      setCardId(card.id);

      setCustomerName(card.customer_name || '');
      setCustomerPhone(card.customer_phone || '');
      setDeliveryAddress(card.delivery_address || '');
      setDeliveryTime(card.delivery_time || '');
      setItems(card.items || []);
      setIsGenerated(true);
      setIsEditing(false);
    } catch (error) {
      console.error(error);
      alert('Could not generate the Action Card. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Inline Item Changes
  const handleItemChange = (index: number, field: keyof Item, value: any) => {
    const updated = [...items];
    if (field === 'quantity') {
      updated[index][field] = Math.max(1, parseInt(value) || 1);
    } else if (field === 'price') {
      updated[index][field] = Math.max(0, parseFloat(value) || 0);
    } else {
      updated[index][field] = value;
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

  // Submit to Database/LocalStorage
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      source: 'audio',
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
      {!isGenerated && !isProcessing && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 space-y-6 shadow-sm text-center">
          <h2 className="text-lg font-bold text-slate-900">Capture Phone Call Order</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Record customer voice logs live. Click start, dictate the order, stop, and process the results.
          </p>

          <div className="flex flex-col items-center justify-center space-y-4">
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
                <button
                  type="button"
                  onClick={handleGenerateActionCard}
                  className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-sm transition-colors cursor-pointer shadow-sm"
                >
                  Generate Action Card
                </button>
              )}
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
                            min="1"
                            placeholder="Qty"
                            value={item.quantity}
                            onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                            className="w-20 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 text-center"
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
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Extracted Order Line Items</h4>
                    <div className="space-y-1.5">
                      {items.map((item, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs p-2 rounded bg-slate-50 border border-slate-100">
                          <div className="text-slate-800 font-medium">
                            <span className="font-bold text-slate-900">{item.quantity}x</span> {item.name}
                          </div>
                          {item.price && (
                            <div className="text-right font-mono text-slate-550 font-bold">
                              ₹{(item.price * item.quantity).toFixed(2)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
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
                <span className="text-lg font-extrabold text-slate-900 font-mono">₹{orderTotal.toFixed(2)}</span>
              </div>
            </div>

            {/* Verification Footer Action Controls */}
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
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-705 text-white font-bold rounded-lg text-sm transition-colors shadow-sm cursor-pointer"
              >
                Submit Order
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
