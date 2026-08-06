'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ClipboardCheck,
  Loader2,
  Mic,
  Plus,
  Sparkles,
  Square,
  Trash2,
} from 'lucide-react';
import {
  createManualActionCard,
  extractActionCardPreview,
  getCatalogItems,
  transcribeAudio,
} from '@/lib/api';
import type { ActionCard, Item } from '@/types';

type FulfilmentType = 'delivery' | 'takeaway' | 'dine_in';

type CatalogItem = {
  id: string;
  display_name: string;
  canonical_name: string;
  base_price: number;
  unit?: string | null;
  active?: boolean;
  in_stock?: boolean;
};

type DraftItem = {
  name: string;
  quantity: number;
  unit: string;
  price: number;
};

const emptyItem = (): DraftItem => ({ name: '', quantity: 1, unit: '', price: 0 });

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

export default function CreateOrderPage() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [catalogError, setCatalogError] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [fulfilment, setFulfilment] = useState<FulfilmentType>('delivery');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [deliveryTime, setDeliveryTime] = useState('');
  const [tableNumber, setTableNumber] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [specialInstructions, setSpecialInstructions] = useState('');
  const [items, setItems] = useState<DraftItem[]>([emptyItem()]);
  const [assistNotes, setAssistNotes] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [formError, setFormError] = useState('');
  const [assistMessage, setAssistMessage] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    let cancelled = false;
    getCatalogItems()
      .then((data) => {
        if (!cancelled) setCatalog(data.filter((item: CatalogItem) => item.active !== false));
      })
      .catch((error) => {
        if (!cancelled) setCatalogError(errorMessage(error, 'Catalog could not be loaded. You can still enter items manually.'));
      });

    return () => {
      cancelled = true;
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const updateItem = (index: number, patch: Partial<DraftItem>) => {
    setItems((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, ...patch } : item
    )));
  };

  const applyCatalogMatch = (index: number, name: string) => {
    const normalized = name.trim().toLowerCase();
    const match = catalog.find((item) => (
      item.display_name.toLowerCase() === normalized || item.canonical_name.toLowerCase() === normalized
    ));
    updateItem(index, match ? {
      name: match.display_name,
      unit: match.unit || '',
      price: Number(match.base_price || 0),
    } : { name });
  };

  const applyPreview = (preview: Partial<ActionCard>) => {
    if (preview.customer_name && preview.customer_name.toLowerCase() !== 'unknown') {
      setCustomerName(preview.customer_name);
    }
    if (preview.customer_phone) setCustomerPhone(preview.customer_phone);
    if (preview.delivery_address) setDeliveryAddress(preview.delivery_address);
    if (preview.delivery_time_normalized || preview.delivery_time) {
      setDeliveryTime(preview.delivery_time_normalized || preview.delivery_time || '');
    }
    if (preview.payment_method) setPaymentMethod(preview.payment_method);
    if (preview.takeaway_delivery_dine_in) {
      const value = preview.takeaway_delivery_dine_in.toLowerCase().replace(/\s+/g, '_');
      if (value === 'delivery' || value === 'takeaway' || value === 'dine_in') setFulfilment(value);
    }
    if (preview.table_number) setTableNumber(preview.table_number);
    if (preview.special_instructions) setSpecialInstructions(preview.special_instructions);
    if (preview.items?.length) {
      setItems(preview.items.map((item: Item) => ({
        name: item.name || '',
        quantity: Number(item.quantity || 1),
        unit: item.unit || '',
        price: Number(item.price || 0),
      })));
    }
  };

  const extractNotes = async (notes = assistNotes) => {
    if (!notes.trim()) {
      setAssistMessage('Enter call notes or record a voice note first.');
      return;
    }
    setIsExtracting(true);
    setAssistMessage('');
    try {
      const preview = await extractActionCardPreview(notes.trim());
      applyPreview(preview);
      setAssistMessage('Draft filled. Review every field before creating the Action Card.');
    } catch (error) {
      setAssistMessage(errorMessage(error, 'AI assist is unavailable. Enter the details manually.'));
    } finally {
      setIsExtracting(false);
    }
  };

  const stopMediaStream = () => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  };

  const startRecording = async () => {
    setAssistMessage('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAssistMessage('Voice capture is not supported in this browser. Enter the order notes manually.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        setIsRecording(false);
        stopMediaStream();
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        if (!blob.size) {
          setAssistMessage('No audio was captured. Enter the order notes manually.');
          return;
        }
        setIsExtracting(true);
        try {
          const extension = recorder.mimeType.includes('ogg') ? 'ogg' : 'webm';
          const file = new File([blob], `owner-order.${extension}`, { type: blob.type });
          const transcription = await transcribeAudio(file);
          setAssistNotes(transcription.transcript);
          const preview = await extractActionCardPreview(transcription.transcript);
          applyPreview(preview);
          setAssistMessage('Voice note transcribed and the draft was filled. Review it before saving.');
        } catch (error) {
          setAssistMessage(errorMessage(error, 'Voice assist is unavailable. Enter the details manually.'));
        } finally {
          setIsExtracting(false);
        }
      };
      recorder.start();
      setIsRecording(true);
    } catch {
      stopMediaStream();
      setAssistMessage('Microphone access was not available. You can enter or paste the order details manually.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
  };

  const validate = () => {
    if (!customerName.trim()) return 'Customer name is required.';
    const validItems = items.filter((item) => item.name.trim() && item.quantity > 0);
    if (!validItems.length) return 'Add at least one item with a valid quantity.';
    if (fulfilment === 'delivery' && !deliveryAddress.trim()) return 'Delivery address is required for delivery orders.';
    if (fulfilment === 'dine_in' && !tableNumber.trim()) return 'Table number is required for dine-in orders.';
    return '';
  };

  const submitOrder = async (event: FormEvent) => {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setIsSubmitting(true);
    setFormError('');
    try {
      const card = await createManualActionCard({
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim(),
        items: items
          .filter((item) => item.name.trim() && item.quantity > 0)
          .map((item) => ({ ...item, name: item.name.trim() })),
        delivery_address: fulfilment === 'delivery' ? deliveryAddress.trim() : '',
        delivery_time: deliveryTime.trim(),
        payment_method: paymentMethod || undefined,
        takeaway_delivery_dine_in: fulfilment,
        table_number: fulfilment === 'dine_in' ? tableNumber.trim() : undefined,
        special_instructions: specialInstructions.trim(),
        status: 'pending',
        source: 'manual',
        message_type: 'ORDER',
        transcript: assistNotes.trim() || 'Manual order entered by owner',
        metadata: { entry_mode: 'owner_manual', requires_owner_review: true },
      });
      router.push(`/action-card?id=${encodeURIComponent(card.id)}`);
    } catch (error) {
      setFormError(errorMessage(error, 'The order could not be created. Your entries are still on this page.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const total = items.reduce((sum, item) => sum + (Number(item.quantity) * Number(item.price)), 0);

  return (
    <main className="min-h-full px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-6xl">
        <button
          type="button"
          onClick={() => router.back()}
          className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-slate-500 transition hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>

        <div className="mb-7 border-b border-slate-200 pb-6">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-700">Owner-assisted intake</p>
          <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">New order</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Capture phone, walk-in, and offline orders. The order stays pending until it is reviewed and approved.
          </p>
        </div>

        <form onSubmit={submitOrder} className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5 flex items-start gap-3">
                <Sparkles className="mt-0.5 h-5 w-5 text-amber-700" />
                <div>
                  <h2 className="font-bold text-slate-900">Optional AI assist</h2>
                  <p className="mt-1 text-sm text-slate-500">Paste call notes or record a short voice note to prefill the form. No order is saved during preview.</p>
                </div>
              </div>
              <textarea
                value={assistNotes}
                onChange={(event) => setAssistNotes(event.target.value)}
                rows={4}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:border-amber-600"
                placeholder="Example: 2 chicken biryani medium spicy, delivery tomorrow 8 PM to Batla House, customer Danish"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => extractNotes()}
                  disabled={isExtracting || isRecording}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isExtracting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Fill from notes
                </button>
                <button
                  type="button"
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={isExtracting}
                  className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isRecording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  {isRecording ? 'Stop recording' : 'Record voice note'}
                </button>
              </div>
              {assistMessage && <p className="mt-3 text-sm text-slate-500" role="status">{assistMessage}</p>}
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 className="mb-5 font-bold text-slate-900">Customer and fulfilment</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold text-slate-700">
                  Customer name <span className="text-red-500">*</span>
                  <input value={customerName} onChange={(event) => setCustomerName(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" placeholder="Customer name" />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Phone number
                  <input value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" inputMode="tel" placeholder="Optional for walk-in orders" />
                </label>
              </div>

              <fieldset className="mt-5">
                <legend className="mb-2 text-sm font-semibold text-slate-700">Fulfilment</legend>
                <div className="grid grid-cols-3 gap-2">
                  {(['delivery', 'takeaway', 'dine_in'] as FulfilmentType[]).map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setFulfilment(option)}
                      className={`min-h-11 rounded-md border px-2 text-sm font-semibold ${fulfilment === option ? 'border-amber-600 bg-amber-50 text-amber-800' : 'border-slate-300 text-slate-600'}`}
                    >
                      {option === 'dine_in' ? 'Dine in' : option.charAt(0).toUpperCase() + option.slice(1)}
                    </button>
                  ))}
                </div>
              </fieldset>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {fulfilment === 'delivery' && (
                  <label className="text-sm font-semibold text-slate-700 sm:col-span-2">
                    Delivery address <span className="text-red-500">*</span>
                    <input value={deliveryAddress} onChange={(event) => setDeliveryAddress(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" placeholder="Full delivery address" />
                  </label>
                )}
                {fulfilment === 'dine_in' && (
                  <label className="text-sm font-semibold text-slate-700">
                    Table number <span className="text-red-500">*</span>
                    <input value={tableNumber} onChange={(event) => setTableNumber(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" placeholder="Table 4" />
                  </label>
                )}
                <label className="text-sm font-semibold text-slate-700">
                  Required time
                  <input value={deliveryTime} onChange={(event) => setDeliveryTime(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" placeholder="Tomorrow, 8:00 PM" />
                </label>
                <label className="text-sm font-semibold text-slate-700">
                  Payment method
                  <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5">
                    <option value="">Not specified</option>
                    <option value="cash">Cash</option>
                    <option value="upi">UPI</option>
                    <option value="card">Card</option>
                    <option value="paid_online">Paid online</option>
                  </select>
                </label>
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-bold text-slate-900">Order items</h2>
                  <p className="mt-1 text-sm text-slate-500">Select catalog items when available so units and prices remain consistent.</p>
                </div>
                <button type="button" onClick={() => setItems((current) => [...current, emptyItem()])} className="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700">
                  <Plus className="h-4 w-4" /> Add item
                </button>
              </div>
              {catalogError && <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{catalogError}</p>}
              <datalist id="catalog-items">
                {catalog.map((item) => <option value={item.display_name} key={item.id}>{item.unit || 'unit'} · ₹{item.base_price}</option>)}
              </datalist>
              <div className="space-y-3">
                {items.map((item, index) => (
                  <div className="grid gap-3 rounded-md border border-slate-200 p-3 sm:grid-cols-[minmax(0,1fr)_90px_100px_110px_40px]" key={index}>
                    <label className="text-xs font-semibold text-slate-500">Item
                      <input list="catalog-items" value={item.name} onChange={(event) => updateItem(index, { name: event.target.value })} onBlur={(event) => applyCatalogMatch(index, event.target.value)} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder="Product or dish" />
                    </label>
                    <label className="text-xs font-semibold text-slate-500">Quantity
                      <input type="number" min="0.01" step="0.01" value={item.quantity} onChange={(event) => updateItem(index, { quantity: Number(event.target.value) })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" />
                    </label>
                    <label className="text-xs font-semibold text-slate-500">Unit
                      <input value={item.unit} onChange={(event) => updateItem(index, { unit: event.target.value })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder="kg, plate" />
                    </label>
                    <label className="text-xs font-semibold text-slate-500">Unit price
                      <input type="number" min="0" step="0.01" value={item.price} onChange={(event) => updateItem(index, { price: Number(event.target.value) })} className="mt-1.5 w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" />
                    </label>
                    <button type="button" onClick={() => setItems((current) => current.length === 1 ? [emptyItem()] : current.filter((_, itemIndex) => itemIndex !== index))} className="mt-5 inline-flex h-10 items-center justify-center rounded-md text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label={`Remove item ${index + 1}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
              <label className="mt-5 block text-sm font-semibold text-slate-700">
                Special instructions
                <textarea value={specialInstructions} onChange={(event) => setSpecialInstructions(event.target.value)} rows={3} className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" placeholder="Dietary notes, substitutions, packing instructions, or customer requests" />
              </label>
            </section>
          </div>

          <aside className="xl:sticky xl:top-6 xl:self-start">
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
                <ClipboardCheck className="h-5 w-5 text-amber-700" />
                <div>
                  <h2 className="font-bold text-slate-900">Review summary</h2>
                  <p className="text-xs text-slate-500">Creates a pending Action Card</p>
                </div>
              </div>
              <dl className="space-y-3 py-4 text-sm">
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Customer</dt><dd className="text-right font-semibold text-slate-800">{customerName || 'Not entered'}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Fulfilment</dt><dd className="font-semibold capitalize text-slate-800">{fulfilment.replace('_', ' ')}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Items</dt><dd className="font-semibold text-slate-800">{items.filter((item) => item.name.trim()).length}</dd></div>
                <div className="flex justify-between gap-3 border-t border-slate-200 pt-3"><dt className="font-semibold text-slate-700">Estimated total</dt><dd className="text-lg font-bold text-slate-900">₹{total.toFixed(2)}</dd></div>
              </dl>
              <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                Review catalog matches, quantity, unit, price, address, and time before submission.
              </p>
              {formError && <p className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">{formError}</p>}
              <button type="submit" disabled={isSubmitting} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardCheck className="h-4 w-4" />}
                Create Action Card
              </button>
            </div>
          </aside>
        </form>
      </div>
    </main>
  );
}
