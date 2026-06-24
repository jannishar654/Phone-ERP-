'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { getActionCards, updateActionCardStatus, updateActionCard, convertActionCardToOrder } from '@/lib/api';
import { ActionCard, Item } from '@/types';

// Main content wrapping the search params logic
function ActionCardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const cardIdParam = searchParams.get('id');

  const [cards, setCards] = useState<ActionCard[]>([]);
  const [selectedCard, setSelectedCard] = useState<ActionCard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit states
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [editTime, setEditTime] = useState('');
  const [editItems, setEditItems] = useState<Item[]>([]);

  // Speech upload demo state
  const [demoTranscript, setDemoTranscript] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractProvider, setExtractProvider] = useState('gemini');

  async function loadCards() {
    try {
      const data = await getActionCards();
      setCards(data);

      // If a card ID was passed in search params, pre-select it
      if (cardIdParam) {
        const found = data.find(c => c.id === cardIdParam);
        if (found) {
          setSelectedCard(found);
        } else if (data.length > 0) {
          setSelectedCard(data[0]);
        }
      } else if (data.length > 0 && !selectedCard) {
        setSelectedCard(data[0]);
      }
    } catch (err: any) {
      setError('Failed to retrieve action cards from FastAPI backend.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }

  const editParam = searchParams.get('edit');

  useEffect(() => {
    loadCards();
  }, [cardIdParam]);

  useEffect(() => {
    if (selectedCard && editParam === 'true') {
      setEditName(selectedCard.customer_name || '');
      setEditPhone(selectedCard.customer_phone || '');
      setEditAddress(selectedCard.delivery_address || '');
      setEditTime(selectedCard.delivery_time || '');
      setEditItems([...selectedCard.items]);
      setIsEditing(true);
    }
  }, [selectedCard, editParam]);

  const selectCard = (card: ActionCard) => {
    setSelectedCard(card);
    setIsEditing(false);
    router.replace(`/action-card?id=${card.id}`);
  };

  const getCardValidationWarning = (card: ActionCard) => {
    const name = (card.customer_name || '').trim();
    if (!name || name.toLowerCase() === 'unknown') {
      return "Customer name is missing.";
    }
    const address = (card.delivery_address || '').trim();
    if (!address) {
      return "Delivery address is missing.";
    }
    const validItems = card.items.filter(i => (i.name || '').trim() !== '');
    if (validItems.length === 0) {
      return "At least one item is required in the order.";
    }
    for (const item of validItems) {
      if (!item.quantity || item.quantity <= 0) {
        return `Quantity for "${item.name}" must be greater than 0.`;
      }
      if (item.price !== undefined && item.price !== null && item.price < 0) {
        return `Price for "${item.name}" cannot be negative.`;
      }
    }
    return null;
  };

  const handleStatusUpdate = async (status: string) => {
    if (!selectedCard) return;

    if (status === 'approved') {
      const warning = getCardValidationWarning(selectedCard);
      if (warning) {
        alert(`Cannot approve card: ${warning}`);
        return;
      }
    }

    try {
      const updated = await updateActionCardStatus(selectedCard.id, status);
      setSelectedCard(updated);
      setCards(cards.map(c => c.id === selectedCard.id ? updated : c));
    } catch (err) {
      alert('Failed to update status on the backend.');
    }
  };

  const handleResolveSuggestion = async (itemIndex: number, action: 'accepted' | 'kept_raw') => {
    if (!selectedCard) return;
    const newItems = [...selectedCard.items];
    const item = newItems[itemIndex];

    if (action === 'accepted') {
      item.name = item.canonical_name || item.name;
      item.resolution_status = 'accepted';
    } else {
      item.name = item.raw_name || item.name;
      item.resolution_status = 'kept_raw';
    }

    try {
      const updated = await updateActionCard(selectedCard.id, { items: newItems });
      setSelectedCard(updated);
      setCards(cards.map(c => c.id === selectedCard.id ? updated : c));
    } catch (err) {
      alert('Failed to update item resolution on the backend.');
    }
  };

  const handleConvertToOrder = async () => {
    if (!selectedCard) return;
    try {
      await convertActionCardToOrder(selectedCard.id);
      alert('Order successfully generated!');
      router.push('/orders');
    } catch (err: any) {
      alert('Failed to convert to order: ' + err.message);
    }
  };

  const startEdit = () => {
    if (!selectedCard) return;
    setEditName(selectedCard.customer_name || '');
    setEditPhone(selectedCard.customer_phone || '');
    setEditAddress(selectedCard.delivery_address || '');
    setEditTime(selectedCard.delivery_time || '');
    setEditItems([...selectedCard.items]);
    setIsEditing(true);
  };

  const handleItemChange = (index: number, field: keyof Item, value: any) => {
    const updated = [...editItems];
    if (field === 'quantity') {
      (updated[index] as any)[field] = Math.max(0.01, parseFloat(value) || 1);
    } else if (field === 'price') {
      (updated[index] as any)[field] = Math.max(0, parseFloat(value) || 0);
    } else {
      (updated[index] as any)[field] = value;
    }
    setEditItems(updated);
  };

  const addEditItemRow = () => {
    setEditItems([...editItems, { name: '', quantity: 1, unit: '', price: 0 }]);
  };

  const removeEditItemRow = (index: number) => {
    if (editItems.length > 1) {
      setEditItems(editItems.filter((_, idx) => idx !== index));
    }
  };

  const saveEdit = async () => {
    if (!selectedCard) return;
    try {
      const validItems = editItems.filter(i => i.name.trim() !== '');
      const updated = await updateActionCard(selectedCard.id, {
        customer_name: editName,
        customer_phone: editPhone,
        delivery_address: editAddress,
        delivery_time: editTime,
        items: validItems
      });
      setSelectedCard(updated);
      setCards(cards.map(c => c.id === selectedCard.id ? updated : c));
      setIsEditing(false);
    } catch (err) {
      alert('Failed to save changes to the backend.');
    }
  };

  // Run a client-side mock transcription/extraction flow when text is typed in the simulation box
  const handleSimulateExtraction = async () => {
    if (!demoTranscript.trim()) return;
    setIsExtracting(true);
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API_BASE_URL}/extract-action-card`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transcript: demoTranscript,
          source: 'text',
          provider: extractProvider,
          save_evaluation: true
        }),
      });
      if (!res.ok) throw new Error();
      const newCard = await res.json();
      setDemoTranscript('');
      loadCards();
      setSelectedCard(newCard);
      router.replace(`/action-card?id=${newCard.id}`);
    } catch (err) {
      alert('Failed to simulate extraction. Ensure FastAPI server is running.');
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Action Cards Board</h1>
        <p className="mt-1 text-sm text-slate-500">
          Inspect order metadata parsed by AI. Validate details, make corrections, and sign off to ERP registry.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Cards List */}
        <div className="lg:col-span-2 space-y-4">
          {isLoading ? (
            <div className="py-12 text-center text-sm text-slate-450">Loading cards...</div>
          ) : error ? (
            <div className="py-12 text-center text-sm text-red-500 font-medium">{error}</div>
          ) : cards.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-500">No cards in system.</div>
          ) : (
            cards.map((card) => (
              <div
                key={card.id}
                onClick={() => selectCard(card)}
                className={`p-6 rounded-xl border transition-all duration-150 cursor-pointer flex flex-col justify-between shadow-xs ${
                  selectedCard?.id === card.id
                    ? 'border-indigo-500 bg-indigo-50/40 shadow-sm'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono text-slate-450 font-bold">{card.id}</span>
                      <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                        card.source === 'audio'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : 'bg-cyan-50 text-cyan-705 border border-cyan-200'
                      }`}>
                        {card.source}
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 mt-1.5">
                      {card.customer_name || 'Anonymous Customer'}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">{card.customer_phone}</p>
                  </div>

                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
                    card.status === 'completed' || card.status === 'delivered'
                      ? 'bg-emerald-50 text-emerald-705 border-emerald-200'
                      : card.status === 'approved'
                      ? 'bg-indigo-50 text-indigo-705 border-indigo-200'
                      : card.status === 'rejected'
                      ? 'bg-red-50 text-red-705 border-red-200'
                      : 'bg-amber-50 text-amber-700 border-amber-300 font-bold'
                  }`}>
                    {card.status === 'pending' && <span className="h-1 w-1 rounded-full bg-amber-500 animate-pulse mr-1"></span>}
                    {card.status}
                  </span>
                </div>

                {/* Items Summary preview */}
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <span className="text-xs text-slate-500 uppercase font-bold tracking-wider">Ordered Items</span>
                  <ul className="mt-2 space-y-1">
                    {card.items.map((item, idx) => (
                      <li key={idx} className="text-sm text-slate-600 flex justify-between font-semibold">
                        <span>{item.quantity}{item.unit ? ` ${item.unit}` : 'x'} {item.name}</span>
                        {item.price !== undefined && item.price !== null && item.price > 0 ? (
                          <span className="text-slate-500 font-mono">₹{(item.price * item.quantity).toFixed(2)}</span>
                        ) : (
                          <span className="text-slate-400 font-medium italic text-[11px]">Price not available</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-4 flex items-center justify-between text-xs text-slate-500 pt-2 font-medium">
                  <span className="truncate max-w-[70%]">Deliver: {card.delivery_address}</span>
                  <span>{new Date(card.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}

          {/* Simulated Speech Transcription Box */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 shadow-sm">
            <h3 className="text-sm font-bold uppercase tracking-wider text-indigo-750">Simulate Call Transcription</h3>
            <p className="text-xs text-slate-500 leading-relaxed font-medium">
              Type or paste sample customer speech transcriptions. Our mock endpoint will simulate AI entity extraction and add a card to the database.
            </p>
            <div>
              <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Extraction Engine</label>
              <select
                value={extractProvider}
                onChange={(e) => setExtractProvider(e.target.value)}
                disabled={isExtracting}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 font-medium focus:outline-none focus:border-indigo-500 mb-2"
              >
                <option value="gemini">Gemini Extraction</option>
                <option value="gliner">GLiNER Extraction</option>
              </select>
            </div>
            <textarea
              rows={3}
              value={demoTranscript}
              onChange={(e) => setDemoTranscript(e.target.value)}
              placeholder='Example: "Hi this is Kathryn Janeway from USS Voyager. Send 5 dilithium crystals to cargo bay 1 ASAP."'
              className="w-full bg-white border border-slate-300 rounded-lg p-3 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 font-medium"
            />
            <button
              onClick={handleSimulateExtraction}
              disabled={isExtracting || !demoTranscript.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-705 disabled:bg-indigo-400 text-white rounded-lg text-xs font-bold shadow-sm cursor-pointer"
            >
              {isExtracting ? 'Extracting...' : 'Parse Speech with AI'}
            </button>
          </div>
        </div>

        {/* Right 1 Col: Detailed Inspect Sidebar Panel */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 self-start min-h-[450px] flex flex-col justify-between shadow-sm">
          {selectedCard ? (
            isEditing ? (
              /* Editing Panel View */
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <h3 className="font-bold text-slate-900">Edit Order Details</h3>
                  <span className="text-xs font-mono text-slate-450 font-bold">{selectedCard.id}</span>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Customer Name</label>
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Phone</label>
                    <input
                      type="text"
                      value={editPhone}
                      onChange={(e) => setEditPhone(e.target.value)}
                      className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Address</label>
                    <input
                      type="text"
                      value={editAddress}
                      onChange={(e) => setEditAddress(e.target.value)}
                      className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Delivery Time</label>
                    <input
                      type="text"
                      value={editTime}
                      onChange={(e) => setEditTime(e.target.value)}
                      className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="pt-2">
                    <div className="flex justify-between items-center mb-1.5">
                      <label className="block text-[10px] uppercase font-bold text-slate-500">Items</label>
                      <button
                        type="button"
                        onClick={addEditItemRow}
                        className="text-[10px] text-indigo-650 font-bold cursor-pointer hover:text-indigo-800"
                      >
                        + Add Item
                      </button>
                    </div>
                    <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                      {editItems.map((item, idx) => (
                        <div key={idx} className="flex gap-2 items-center">
                          <input
                            type="text"
                            placeholder="Item"
                            value={item.name}
                            onChange={(e) => handleItemChange(idx, 'name', e.target.value)}
                            className="flex-1 bg-white border border-slate-300 rounded px-2 py-1 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
                          />
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            placeholder="Qty"
                            value={item.quantity === null || ['none', 'null', 'missing', 'unknown'].includes(String(item.quantity).toLowerCase()) ? '' : item.quantity}
                            onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                            className="w-10 bg-white border border-slate-300 rounded px-2 py-1 text-xs text-slate-900 text-center font-medium focus:outline-none focus:border-indigo-500"
                          />
                          <input
                            type="text"
                            placeholder="Unit"
                            value={['none', 'null', 'missing', 'unknown'].includes(String(item.unit || '').toLowerCase()) ? '' : (item.unit || '')}
                            onChange={(e) => handleItemChange(idx, 'unit', e.target.value)}
                            className="w-14 bg-white border border-slate-300 rounded px-2 py-1 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-500"
                          />
                          <input
                            type="number"
                            step="0.01"
                            placeholder="Price"
                            value={item.price || ''}
                            onChange={(e) => handleItemChange(idx, 'price', e.target.value)}
                            className="w-14 bg-white border border-slate-300 rounded px-2 py-1 text-xs text-slate-900 text-right font-mono focus:outline-none focus:border-indigo-500"
                          />
                          <button
                            type="button"
                            onClick={() => removeEditItemRow(idx)}
                            disabled={editItems.length === 1}
                            className="text-slate-400 hover:text-red-650 disabled:opacity-35 cursor-pointer font-extrabold text-sm"
                          >
                            &times;
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100 flex gap-2">
                  <button
                    onClick={() => setIsEditing(false)}
                    className="flex-1 px-3 py-2 border border-slate-300 hover:bg-slate-50 text-slate-600 hover:text-slate-900 rounded text-xs font-bold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveEdit}
                    className="flex-1 px-3 py-2 bg-indigo-600 hover:bg-indigo-705 text-white rounded text-xs font-bold cursor-pointer"
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            ) : (
              /* Inspect Details Panel View */
              <div className="space-y-6">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-slate-450 font-bold">{selectedCard.id}</span>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold border ${
                      selectedCard.status === 'completed' || selectedCard.status === 'delivered'
                        ? 'bg-emerald-50 text-emerald-705 border-emerald-200 uppercase tracking-wider'
                        : selectedCard.status === 'approved'
                        ? 'bg-indigo-50 text-indigo-750 border-indigo-200 uppercase tracking-wider'
                        : selectedCard.status === 'rejected'
                        ? 'bg-red-50 text-red-705 border-red-200 uppercase tracking-wider'
                        : 'bg-amber-50 text-amber-700 border-amber-300 font-bold uppercase tracking-wider shadow-3xs'
                    }`}>
                      {selectedCard.status === 'pending' && <span className="h-1 w-1 rounded-full bg-amber-500 animate-pulse mr-1"></span>}
                      {selectedCard.status}
                    </span>
                  </div>
                  <h2 className="text-xl font-extrabold text-slate-900 mt-2 flex items-center gap-2">
                    {selectedCard.customer_name || 'Anonymous'}
                    {selectedCard.message_type && (
                      <span className={`text-[10px] px-2 py-0.5 rounded border uppercase tracking-wider font-bold ${
                        selectedCard.message_type === 'COMPLAINT' || selectedCard.message_type === 'CANCEL'
                        ? 'bg-red-100 text-red-800 border-red-300'
                        : selectedCard.message_type === 'RETURN'
                        ? 'bg-orange-100 text-orange-800 border-orange-300'
                        : 'bg-indigo-100 text-indigo-800 border-indigo-300'
                      }`}>
                        {selectedCard.message_type}
                      </span>
                    )}
                  </h2>
                  <p className="text-sm text-indigo-650 font-bold mt-0.5 flex justify-between items-center">
                    <span>{selectedCard.customer_phone || 'No phone number provided'}</span>
                    {selectedCard.confidence_score !== undefined && selectedCard.confidence_label ? (
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                        selectedCard.confidence_label === 'High' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                        selectedCard.confidence_label === 'Medium' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                        'bg-red-100 text-red-800 border-red-300'
                      }`}>
                        Confidence: {selectedCard.confidence_score}% {selectedCard.confidence_label}
                      </span>
                    ) : selectedCard.confidence !== undefined && (
                      <span className="text-[10px] text-slate-500 font-medium bg-slate-100 px-1.5 py-0.5 rounded">
                        Confidence: {(selectedCard.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </p>
                </div>
                
                {selectedCard.confidence_reasons && selectedCard.confidence_reasons.length > 0 && (
                  <div className={`p-2 rounded mt-2 border ${
                    selectedCard.confidence_label === 'High' ? 'bg-emerald-50 border-emerald-200' :
                    selectedCard.confidence_label === 'Medium' ? 'bg-amber-50 border-amber-200' :
                    'bg-red-50 border-red-200'
                  }`}>
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Review Reasons:</h4>
                    <ul className="text-xs space-y-0.5 pl-3 list-disc">
                      {selectedCard.confidence_reasons.map((reason, idx) => (
                        <li key={idx} className={
                          selectedCard.confidence_label === 'High' ? 'text-emerald-700' :
                          selectedCard.confidence_label === 'Medium' ? 'text-amber-700' : 
                          'text-red-700'
                        }>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="space-y-3">
                  <div>
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Delivery Instructions</h4>
                    <p className="text-sm text-slate-800 mt-1 font-bold">{selectedCard.delivery_address || 'Not specified'}</p>
                    <div className="mt-0.5">
                      <p className="text-xs text-slate-500 font-semibold">Time: {selectedCard.delivery_time || 'Immediate'}</p>
                      {selectedCard.delivery_time_raw && (
                        <p className="text-[10px] text-slate-400 font-medium italic mt-0.5">Original delivery time: "{selectedCard.delivery_time_raw}"</p>
                      )}
                      {selectedCard.delivery_time_warning && (
                        <p className="text-[10px] text-amber-600 font-semibold mt-0.5 flex items-center gap-1">
                          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          {selectedCard.delivery_time_warning}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-100">
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Payment Details</h4>
                    <p className={`text-xs mt-1 font-bold ${
                      selectedCard.payment_method === 'Credit (Udhaar)' ? 'text-red-650' :
                      selectedCard.payment_method === 'Cash' || selectedCard.payment_method === 'Online' ? 'text-emerald-650' :
                      'text-slate-600'
                    }`}>
                      {selectedCard.payment_method || 'Not Specified'}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-100">
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Order Items</h4>
                    <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                      {selectedCard.items.map((item, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs p-2 rounded bg-slate-50 border border-slate-100 shadow-3xs">
                          <div className="text-slate-800 font-medium">
                            {(() => {
                              const isQtyMissing = item.quantity === null || item.quantity === undefined || ['none', 'null', 'missing', 'unknown'].includes(String(item.quantity).toLowerCase());
                              const isUnitMissing = !item.unit || ['none', 'null', 'missing', 'unknown'].includes(String(item.unit).toLowerCase());

                              if (isQtyMissing) {
                                return <span className="font-bold text-amber-600 bg-amber-50 px-1 py-0.5 rounded border border-amber-200 mr-1.5">Missing Qty</span>;
                              }
                              return (
                                <span className="font-bold text-slate-900 mr-1">
                                  {item.quantity}{!isUnitMissing ? ` ${item.unit}` : 'x'}
                                </span>
                              );
                            })()}
                            <span className="font-bold">{item.raw_name || item.name}</span>
                            {item.resolution_status === 'suggested' && item.canonical_name && (
                              <div className="mt-1 text-[10px] text-blue-600 font-bold flex flex-wrap items-center gap-1">
                                <span className="bg-blue-50 border border-blue-200 px-1 rounded">Suggested: {item.canonical_name}</span>
                                <span className="text-slate-500 font-normal ml-1">
                                  <button className="underline hover:text-blue-800 font-semibold" onClick={(e) => { e.preventDefault(); handleResolveSuggestion(idx, 'accepted'); }}>Accept</button> |
                                  <button className="underline hover:text-blue-800 ml-1" onClick={(e) => { e.preventDefault(); handleResolveSuggestion(idx, 'kept_raw'); }}>Keep spoken</button>
                                </span>
                              </div>
                            )}
                            {item.alias_used && item.canonical_name && (
                              <div className="mt-0.5 text-[9px] text-emerald-600 font-bold">
                                Auto-applied alias: {item.canonical_name}
                              </div>
                            )}
                          </div>
                          {item.price !== undefined && item.price !== null && item.price > 0 ? (
                            <div className="text-right font-mono text-slate-500 font-bold">
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
                    {(() => {
                      const orderTotal = selectedCard.items.reduce((sum, item) => sum + ((item.quantity || 0) * (item.price || 0)), 0);
                      const hasMissingPrice = selectedCard.items.some(item => item.price === undefined || item.price === null || item.price <= 0);
                      return (
                        <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col sm:flex-row sm:justify-between items-start sm:items-center gap-2 text-sm font-semibold text-slate-600">
                          <span className="text-slate-500 text-xs uppercase tracking-wider">Calculated Grand Total</span>
                          <div className="flex flex-col sm:flex-row items-end sm:items-center gap-2">
                            <span className="text-base sm:text-lg font-black text-slate-900 font-mono bg-slate-50 border border-slate-150 px-3 py-1 rounded">
                              ₹{orderTotal.toFixed(2)}
                            </span>
                            {hasMissingPrice && (
                              <span className="text-amber-600 font-bold text-[10px] sm:text-xs italic bg-amber-50 px-2 py-1 rounded border border-amber-200">
                                + Pending Price Verification
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {selectedCard.metadata?.cancelled_items?.length > 0 && (
                    <div className="pt-2 border-t border-slate-100">
                      <h4 className="text-[10px] font-bold text-red-600 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                        Cancelled Items
                      </h4>
                      <ul className="text-xs text-red-700 font-medium list-disc pl-4 space-y-0.5">
                        {selectedCard.metadata?.cancelled_items.map((ci: any, idx: number) => (
                          <li key={idx}>
                            <span className="font-bold">{ci.name}</span>
                            {ci.evidence && <span className="text-[10px] text-red-500 italic block">"{ci.evidence}"</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {selectedCard.metadata?.return_items?.length > 0 && (
                    <div className="pt-2 border-t border-slate-100">
                      <h4 className="text-[10px] font-bold text-orange-600 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                        </svg>
                        Return Requested
                      </h4>
                      <ul className="text-xs text-orange-700 font-medium list-disc pl-4 space-y-0.5">
                        {selectedCard.metadata?.return_items.map((ri: any, idx: number) => (
                          <li key={idx}>
                            <span className="font-bold">{ri.quantity} {ri.unit} {ri.name}</span>
                            {ri.evidence && <span className="text-[10px] text-orange-500 italic block">"{ri.evidence}"</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {selectedCard.metadata?.substitution_instructions?.length > 0 && (
                    <div className="pt-2 border-t border-slate-100">
                      <h4 className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                        </svg>
                        Substitution Instructions
                      </h4>
                      <ul className="text-xs text-indigo-700 font-medium list-disc pl-4 space-y-0.5">
                        {selectedCard.metadata?.substitution_instructions.map((si: any, idx: number) => (
                          <li key={idx}>
                            <span className="font-bold">{si.name}</span> - {si.condition}
                            {si.evidence && <span className="text-[10px] text-indigo-500 italic block">"{si.evidence}"</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {selectedCard.metadata?.previous_order_reference && (
                    <div className="pt-2 border-t border-slate-100">
                      <h4 className="text-[10px] font-bold text-purple-600 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Previous Order Reference
                      </h4>
                      <p className="text-xs text-purple-700 font-medium pl-1">
                        Manual review required: <span className="italic">"{selectedCard.metadata?.previous_order_reference}"</span>
                      </p>
                    </div>
                  )}

                  {selectedCard.transcript && (
                    <div className="pt-2 border-t border-slate-100">
                      <div className="flex justify-between items-center mb-2">
                        <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Original AI Transcript</h4>
                        {selectedCard.metadata?.pipeline && (
                          <span className="text-[9px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono border border-slate-200">
                            Pipeline: {selectedCard.metadata.pipeline}
                          </span>
                        )}
                      </div>
                      <blockquote className="mt-1 text-xs text-slate-650 bg-slate-50 p-3 rounded border border-slate-150 italic leading-relaxed font-medium">
                        "{selectedCard.transcript}"
                      </blockquote>

                      {selectedCard.metadata?.extraction_notes && (
                        <div className="mt-2 text-[10px] text-slate-600 bg-blue-50 p-2 rounded border border-blue-100 flex items-start gap-1.5">
                          <svg className="h-3 w-3 text-blue-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <div><span className="font-bold">Extraction Notes:</span> {selectedCard.metadata.extraction_notes}</div>
                        </div>
                      )}

                      {selectedCard.metadata?.multi_card_notes && (
                        <div className="mt-1 text-[10px] text-amber-700 bg-amber-50 p-2 rounded border border-amber-200 flex items-start gap-1.5">
                          <svg className="h-3 w-3 text-amber-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          <div><span className="font-bold">Multi-card Warning:</span> {selectedCard.metadata.multi_card_notes}</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-100 space-y-2">
                  {selectedCard.risk_flags && selectedCard.risk_flags.length > 0 && (
                    <div className="bg-red-50 border border-red-200 p-3 rounded-lg text-[10px] text-red-800 font-semibold leading-relaxed flex items-start gap-2 my-2">
                      <svg className="h-4 w-4 text-red-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <div>
                        <span className="font-extrabold uppercase mr-1">Risk Detected:</span>
                        {selectedCard.risk_flags.join(", ")}
                      </div>
                    </div>
                  )}

                  {selectedCard.missing_fields && selectedCard.missing_fields.length > 0 && (
                    <div className="bg-amber-50 border border-amber-250 p-3 rounded-lg text-[10px] text-amber-850 font-semibold leading-relaxed flex items-start gap-2 my-2">
                      <svg className="h-4 w-4 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <div>
                        <span className="font-extrabold uppercase mr-1">Missing details:</span>
                        {selectedCard.missing_fields.join(", ")}
                      </div>
                    </div>
                  )}

                  {selectedCard.validation_warnings && selectedCard.validation_warnings.length > 0 && (
                    <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg text-[10px] text-slate-700 font-semibold leading-relaxed flex items-start gap-2 my-2">
                      <svg className="h-4 w-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        <span className="font-extrabold uppercase mr-1">Validation Warnings:</span>
                        {selectedCard.validation_warnings.join(" ")}
                      </div>
                    </div>
                  )}
                  {getCardValidationWarning(selectedCard) && (
                    <div className="text-sm text-amber-705 font-semibold flex items-center justify-start text-left gap-2 py-1 my-2">
                      <span className="text-amber-500 text-base shrink-0">⚠</span>
                      <span>
                        <span className="font-bold">{getCardValidationWarning(selectedCard)}</span>{' '}
                        <span className="text-amber-600 font-medium">Please edit the order card to resolve.</span>
                      </span>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleStatusUpdate('approved')}
                      disabled={selectedCard.status === 'approved' || !!getCardValidationWarning(selectedCard)}
                      className="flex-1 px-3 py-2 bg-emerald-650 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-emerald-650 text-white rounded text-xs font-bold cursor-pointer transition-colors shadow-xs"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleStatusUpdate('rejected')}
                      disabled={selectedCard.status === 'rejected'}
                      className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-550 disabled:opacity-40 disabled:hover:bg-red-600 text-white rounded text-xs font-bold cursor-pointer transition-colors shadow-xs"
                    >
                      Reject
                    </button>
                  </div>
                  <button
                    onClick={startEdit}
                    className="w-full px-3 py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded text-xs font-bold border border-slate-200 cursor-pointer transition-colors shadow-3xs"
                  >
                    Edit Order Card
                  </button>
                  
                  {selectedCard.status === 'approved' && (
                    <div className="pt-2">
                      <button
                        onClick={handleConvertToOrder}
                        className="w-full px-3 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-bold cursor-pointer transition-colors shadow-md"
                      >
                        Generate Final Bill / Order
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          ) : (
            <div className="flex flex-col items-center justify-center text-center h-[350px] text-slate-400">
              <svg className="h-12 w-12 text-slate-350 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
              </svg>
              <h3 className="text-sm font-bold text-slate-900">Select an Action Card</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-[200px] font-medium leading-relaxed">
                Click on any action card to inspect full details, edit data or confirm to ERP system.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ActionCardPage() {
  return (
    <Suspense fallback={<div className="py-12 text-center text-sm text-slate-450 font-bold">Loading action cards...</div>}>
      <ActionCardContent />
    </Suspense>
  );
}
