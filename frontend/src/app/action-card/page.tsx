'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { getActionCards, updateActionCardStatus, updateActionCard } from '@/lib/api';
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
      return "Customer Name is required and cannot be 'Unknown'.";
    }
    const address = (card.delivery_address || '').trim();
    if (!address) {
      return "Delivery Address is required.";
    }
    const validItems = card.items.filter(i => (i.name || '').trim() !== '');
    if (validItems.length === 0) {
      return "At least one valid item name is required.";
    }
    for (const item of validItems) {
      if (!item.quantity || item.quantity <= 0) {
        return `Item "${item.name}" must have a quantity of 1 or more.`;
      }
      if (item.price !== undefined && item.price !== null && item.price < 0) {
        return `Item "${item.name}" cannot have a negative price.`;
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
      updated[index][field] = Math.max(1, parseInt(value) || 1);
    } else if (field === 'price') {
      updated[index][field] = Math.max(0, parseFloat(value) || 0);
    } else {
      updated[index][field] = value;
    }
    setEditItems(updated);
  };

  const addEditItemRow = () => {
    setEditItems([...editItems, { name: '', quantity: 1, price: 0 }]);
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
        body: JSON.stringify({ transcript: demoTranscript, source: 'audio' }),
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
                      : 'bg-amber-50 text-amber-705 border-amber-250'
                  }`}>
                    {card.status}
                  </span>
                </div>

                {/* Items Summary preview */}
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <span className="text-xs text-slate-500 uppercase font-bold tracking-wider">Ordered Items</span>
                  <ul className="mt-2 space-y-1">
                    {card.items.map((item, idx) => (
                      <li key={idx} className="text-sm text-slate-600 flex justify-between font-semibold">
                        <span>{item.quantity}x {item.name}</span>
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
                            min="1"
                            placeholder="Qty"
                            value={item.quantity}
                            onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                            className="w-10 bg-white border border-slate-300 rounded px-2 py-1 text-xs text-slate-900 text-center font-medium focus:outline-none focus:border-indigo-500"
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
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
                      selectedCard.status === 'completed' || selectedCard.status === 'delivered'
                        ? 'bg-emerald-50 text-emerald-705 border-emerald-200'
                        : selectedCard.status === 'approved'
                        ? 'bg-indigo-50 text-indigo-750 border-indigo-200'
                        : selectedCard.status === 'rejected'
                        ? 'bg-red-50 text-red-705 border-red-200'
                        : 'bg-amber-50 text-amber-705 border-amber-250'
                    }`}>
                      {selectedCard.status}
                    </span>
                  </div>
                  <h2 className="text-xl font-extrabold text-slate-900 mt-2">{selectedCard.customer_name || 'Anonymous'}</h2>
                  <p className="text-sm text-indigo-650 font-bold mt-0.5">{selectedCard.customer_phone || 'No phone number provided'}</p>
                </div>

                <div className="space-y-3">
                  <div>
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Delivery Instructions</h4>
                    <p className="text-sm text-slate-800 mt-1 font-bold">{selectedCard.delivery_address || 'Not specified'}</p>
                    <p className="text-xs text-slate-500 mt-0.5 font-semibold">Time: {selectedCard.delivery_time || 'Immediate'}</p>
                  </div>

                  <div className="pt-2 border-t border-slate-100">
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Order Line Items</h4>
                    <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                      {selectedCard.items.map((item, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs p-2 rounded bg-slate-50 border border-slate-100 shadow-3xs">
                          <div className="text-slate-800 font-medium">
                            <span className="font-bold text-slate-900">{item.quantity}x</span> {item.name}
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
                  </div>

                  {selectedCard.transcript && (
                    <div className="pt-2 border-t border-slate-100">
                      <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Original AI Transcript</h4>
                      <blockquote className="mt-2 text-xs text-slate-650 bg-slate-50 p-3 rounded border border-slate-150 italic leading-relaxed font-medium">
                        "{selectedCard.transcript}"
                      </blockquote>
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-100 space-y-2">
                  {getCardValidationWarning(selectedCard) && (
                    <div className="bg-amber-50 border border-amber-250 p-3 rounded-lg text-[10px] text-amber-850 font-semibold leading-relaxed flex items-start gap-2 my-2">
                      <svg className="h-4 w-4 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <div>
                        <span className="font-extrabold uppercase mr-1">[Warning]</span>
                        {getCardValidationWarning(selectedCard)} Please edit order card to resolve.
                      </div>
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
