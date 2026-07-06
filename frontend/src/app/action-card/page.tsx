'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { getActionCards, updateActionCardStatus, updateActionCard, convertActionCardToOrder } from '@/lib/api';
import { ActionCard, Item } from '@/types';
import { format } from 'date-fns';
import { Calendar as CalendarIcon, Phone, MapPin, Clock } from 'lucide-react';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

const formatDeliveryTime = (value: string | undefined): string => {
  if (!value) return 'Immediate';
  const trimmed = value.trim();
  if (trimmed.toLowerCase() === 'immediate' || trimmed === '') return 'Immediate';

  // Parse YYYY-MM-DD hh:mm AM/PM or YYYY-MM-DD HH:mm
  const dateMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2})(?:\s*(AM|PM|am|pm))?)?/i);
  if (dateMatch) {
    const [_, y, m, d, hh, mm, ampm] = dateMatch;

    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const monthName = months[parseInt(m, 10) - 1] || m;
    const dayStr = `${d} ${monthName}`;

    if (hh && mm) {
      const timeStr = ampm ? `${hh}:${mm} ${ampm.toUpperCase()}` : `${hh}:${mm}`;
      return `${dayStr} • ${timeStr}`;
    }
    return dayStr;
  }

  return trimmed;
};

const getStatusBadgeClass = (status: string) => {
  const base = "inline-flex items-center justify-center rounded-full h-6 px-3 text-[10px] font-bold uppercase tracking-wider border shadow-3xs transition-all";
  switch (status?.toLowerCase()) {
    case 'completed':
    case 'delivered':
    case 'converted':
      return `${base} bg-emerald-500 text-white border-emerald-600`;
    case 'approved':
      return `${base} bg-indigo-600 text-white border-indigo-700`;
    case 'rejected':
      return `${base} bg-red-600 text-white border-red-700`;
    case 'pending':
    default:
      return `${base} bg-amber-500 text-white border-amber-600`;
  }
};


interface CustomDateTimePickerProps {
  value: string;
  onChange: (val: string) => void;
}

function CustomDateTimePicker({ value, onChange }: CustomDateTimePickerProps) {
  const dateMatch = value ? value.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?/i) : null;

  let dateVal: Date | undefined = undefined;
  let hourVal: string = "";
  let minuteVal: string = "";
  let ampmVal: string = "";

  if (dateMatch) {
    const [_, y, m, d, hh, mm, ampm] = dateMatch;
    dateVal = new Date(parseInt(y, 10), parseInt(m, 10) - 1, parseInt(d, 10));
    hourVal = hh;
    minuteVal = mm;
    ampmVal = ampm?.toUpperCase() || "AM";
  }

  const hoursOptions = Array.from({ length: 12 }, (_, i) => String(i + 1));
  const minutesOptions = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));

  const updateValue = (d: Date | undefined, h: string, m: string, ap: string) => {
    if (!d) {
      onChange("Immediate");
      return;
    }
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = h || "12";
    const mm = m || "00";
    const ampm = ap || "AM";
    onChange(`${year}-${month}-${day} ${hh}:${mm} ${ampm}`);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 items-center">
        {/* Popover Date Selection */}
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="flex-1 flex items-center justify-between bg-white border border-slate-300 hover:border-slate-400 rounded-lg px-3 py-2 text-xs font-bold text-slate-700 cursor-pointer transition-all shadow-3xs"
            >
              <span className="flex items-center gap-2">
                <CalendarIcon className="h-4 w-4 text-slate-400" />
                {dateVal ? format(dateVal, "PPP") : "Select Date"}
              </span>
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="single"
              selected={dateVal}
              onSelect={(d) => updateValue(d, hourVal || "12", minuteVal || "00", ampmVal || "AM")}
            />
          </PopoverContent>
        </Popover>

        {/* Time Select Dropdowns */}
        <div className="flex gap-1.5 items-center">
          <select
            value={hourVal}
            onChange={(e) => updateValue(dateVal || new Date(), e.target.value, minuteVal || "00", ampmVal || "AM")}
            className="bg-white border border-slate-300 hover:border-slate-400 rounded-lg px-2 py-2 text-xs font-bold text-slate-750 focus:outline-none focus:border-indigo-500 cursor-pointer transition-all shadow-3xs"
          >
            <option value="">Hour</option>
            {hoursOptions.map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
          <span className="text-slate-400 font-bold">:</span>
          <select
            value={minuteVal}
            onChange={(e) => updateValue(dateVal || new Date(), hourVal || "12", e.target.value, ampmVal || "AM")}
            className="bg-white border border-slate-350 hover:border-slate-400 rounded-lg px-2 py-2 text-xs font-bold text-slate-750 focus:outline-none focus:border-indigo-500 cursor-pointer transition-all shadow-3xs"
          >
            <option value="">Min</option>
            {minutesOptions.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          <select
            value={ampmVal}
            onChange={(e) => updateValue(dateVal || new Date(), hourVal || "12", minuteVal || "00", e.target.value)}
            className="bg-white border border-slate-350 hover:border-slate-400 rounded-lg px-2 py-2 text-xs font-bold text-slate-750 focus:outline-none focus:border-indigo-500 cursor-pointer transition-all shadow-3xs"
          >
            <option value="AM">AM</option>
            <option value="PM">PM</option>
          </select>
        </div>
      </div>

      {value && value !== 'Immediate' && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onChange("")}
            className="text-[10px] text-slate-500 hover:text-slate-700 font-bold cursor-pointer transition-colors"
          >
            ✕ Clear
          </button>
        </div>
      )}
    </div>
  );
}

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

  // Collapsible AI Analysis state
  const [isAiAnalysisExpanded, setIsAiAnalysisExpanded] = useState(false);

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
  }, []);

  useEffect(() => {
    if (cards.length > 0 && cardIdParam) {
      const found = cards.find(c => c.id === cardIdParam);
      if (found && (!selectedCard || selectedCard.id !== found.id)) {
        setSelectedCard(found);
      }
    }
  }, [cardIdParam, cards]);

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
    setIsAiAnalysisExpanded(false);
    router.replace(`/action-card?id=${card.id}`, { scroll: false });
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

  const isDayMissing = (card: ActionCard) => {
    const warning = card.delivery_time_warning?.toLowerCase() || '';
    return warning.includes('day') || warning.includes('date') || (!card.delivery_time_normalized && card.delivery_time_raw);
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
      let finalDeliveryTime = editTime;
      if (!finalDeliveryTime || finalDeliveryTime.trim() === '') {
        finalDeliveryTime = 'Immediate';
      }

      // Past check warning
      const dateMatch = finalDeliveryTime.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?/i);
      if (dateMatch) {
        const [_, y, m, d, hh, mm, ampm] = dateMatch;
        let hour = parseInt(hh, 10);
        if (ampm) {
          const up = ampm.toUpperCase();
          if (up === 'PM' && hour < 12) hour += 12;
          if (up === 'AM' && hour === 12) hour = 0;
        }
        const selectedDate = new Date(parseInt(y, 10), parseInt(m, 10) - 1, parseInt(d, 10), hour, parseInt(mm, 10));
        const checkTime = new Date();
        checkTime.setMinutes(checkTime.getMinutes() - 5);
        if (selectedDate < checkTime) {
          alert('Warning: The selected delivery date and time is in the past. Saving anyway.');
        }
      }

      const updated = await updateActionCard(selectedCard.id, {
        customer_name: editName,
        customer_phone: editPhone,
        delivery_address: editAddress,
        delivery_time: finalDeliveryTime,
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
    <div className="space-y-4">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Action Cards Board</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
        {/* Left 3 Cols: Cards List */}
        <div className="lg:col-span-3 space-y-4 lg:max-h-[calc(100vh-200px)] lg:overflow-y-auto pr-3">
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
                id={`card-${card.id}`}
                onClick={() => selectCard(card)}
                className={`p-3 rounded-xl border transition-all duration-150 cursor-pointer flex flex-col justify-between shadow-3xs ${selectedCard?.id === card.id
                    ? 'border-indigo-500 bg-indigo-50/40 shadow-xs'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50 hover:shadow-xs'
                  }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-1.5 leading-none">
                      <span className="text-[9px] font-mono text-slate-400 font-bold">{card.id}</span>
                      <span className="text-[9px] font-mono text-slate-400 font-bold">•</span>
                      <span className="text-[9px] font-mono text-slate-400 font-bold">{new Date(card.created_at).toLocaleDateString()}</span>
                      <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-extrabold uppercase tracking-wider ${card.source === 'audio'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : 'bg-cyan-50 text-cyan-700 border border-cyan-200'
                        }`}>
                        {card.source}
                      </span>
                    </div>
                    <h3 className="text-base font-extrabold text-slate-900 truncate mt-1">
                      {card.customer_name || 'Anonymous Customer'}
                    </h3>
                    {card.customer_phone && (
                      <p className="text-[11px] text-slate-500 font-bold mt-0.5">{card.customer_phone}</p>
                    )}
                  </div>

                  <span className={getStatusBadgeClass(card.status)}>
                    {card.status === 'pending' && <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse mr-1.5"></span>}
                    {card.status}
                  </span>
                </div>

                {/* Ordered Items Summary */}
                <div className="mt-2 pt-2 border-t border-slate-100">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">Ordered Items</span>
                  <ul className="space-y-0.5">
                    {card.items.map((item, idx) => (
                      <li key={idx} className="text-xs text-slate-650 flex justify-between font-semibold">
                        <span>{item.quantity}{item.unit ? ` ${item.unit}` : 'x'} {item.name}</span>
                        {item.price !== undefined && item.price !== null && item.price > 0 ? (
                          <span className="text-slate-500 font-mono">₹{(item.price * item.quantity).toFixed(2)}</span>
                        ) : (
                          <span className="text-slate-400 italic text-[10px]">Price pending</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Delivery Information */}
                <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-slate-600 gap-4">
                  <span className="truncate max-w-[55%] flex items-center gap-1" title={card.delivery_address}>
                    <span className="text-slate-400 text-[10px] uppercase font-bold">Where:</span>
                    <span className="text-slate-800 truncate">{card.delivery_address || 'Not specified'}</span>
                  </span>
                  <span className="flex items-center gap-1 max-w-[42%] truncate shrink-0">
                    <span className="text-slate-400 text-[10px] uppercase font-bold">When:</span>
                    <span className="text-slate-800 truncate">{formatDeliveryTime(card.delivery_time)}</span>
                    {isDayMissing(card) && (
                      <span className="text-amber-650 font-black text-xs cursor-help shrink-0" title="Delivery day not specified">⚠</span>
                    )}
                  </span>
                </div>
              </div>
            ))
          )}


        </div>

        {/* Right 2 Cols: Detailed Inspect Sidebar Panel */}
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5 pr-4 sticky top-4 lg:max-h-[calc(100vh-200px)] lg:overflow-y-auto self-start min-h-[450px] flex flex-col justify-between shadow-sm">
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
                    <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1.5">Delivery Time</label>
                    <CustomDateTimePicker
                      value={editTime}
                      onChange={(val) => setEditTime(val)}
                    />
                  </div>

                  <div className="pt-2">
                    <div className="flex justify-between items-center mb-1.5">
                      <label className="block text-[10px] uppercase font-bold text-slate-500">Items</label>
                      <button
                        type="button"
                        onClick={addEditItemRow}
                        className="text-[10px] text-indigo-600 font-bold cursor-pointer hover:text-indigo-800"
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
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-slate-400 font-bold">{selectedCard.id}</span>
                    <span className={getStatusBadgeClass(selectedCard.status)}>
                      {selectedCard.status === 'pending' && <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse mr-1.5"></span>}
                      {selectedCard.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mt-1.5 items-center">
                    <div className="flex items-baseline gap-2 min-w-0">
                      <h2 className="text-xl font-extrabold text-slate-900 leading-none truncate">
                        {selectedCard.customer_name || 'Anonymous'}
                      </h2>
                      {selectedCard.message_type && selectedCard.message_type !== 'ORDER' && (
                        <span className={`text-[10px] px-2 py-0.5 rounded border uppercase tracking-wider font-bold shrink-0 leading-none ${selectedCard.message_type === 'COMPLAINT' || selectedCard.message_type === 'CANCEL'
                            ? 'bg-red-100 text-red-800 border-red-300'
                            : selectedCard.message_type === 'RETURN'
                              ? 'bg-orange-100 text-orange-800 border-orange-300'
                              : 'bg-indigo-100 text-indigo-800 border-indigo-300'
                          }`}>
                          {selectedCard.message_type}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 min-w-0">
                      <Phone className="h-4 w-4 text-indigo-500 shrink-0" />
                      <span className="text-xs text-indigo-655 font-bold truncate">
                        {selectedCard.customer_phone || 'No phone number'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4 pb-2 border-b border-slate-100 text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <MapPin className="h-4 w-4 text-slate-400 shrink-0" />
                      <span className="text-xs text-slate-800 font-bold truncate" title={selectedCard.delivery_address}>
                        {selectedCard.delivery_address || 'Not specified'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 min-w-0">
                      <Clock className="h-4 w-4 text-slate-400 shrink-0" />
                      <div className="min-w-0 flex flex-col justify-center">
                        <span className="text-xs text-slate-800 font-bold truncate">
                          {formatDeliveryTime(selectedCard.delivery_time)}
                        </span>
                        {isDayMissing(selectedCard) && (
                          <span className="text-[9px] text-amber-600 font-bold leading-none mt-0.5">
                            ⚠ Delivery day not specified
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Payment</span>
                    <span className={`font-bold ${selectedCard.payment_method === 'Credit (Udhaar)' ? 'text-red-600' :
                        selectedCard.payment_method === 'Cash' || selectedCard.payment_method === 'Online' ? 'text-emerald-600' :
                          'text-slate-600'
                      }`}>
                      {selectedCard.payment_method || 'Not Specified'}
                    </span>
                  </div>

                  <div className="pt-2 border-t border-slate-100">
                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Order Items</h4>
                    <div className="space-y-2">
                      {selectedCard.items.map((item, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-150 shadow-3xs hover:bg-slate-50/70 transition-colors">
                          <div className="text-slate-800 font-semibold flex items-center min-w-0 pr-2">
                            {(() => {
                              const isQtyMissing = item.quantity === null || item.quantity === undefined || ['none', 'null', 'missing', 'unknown'].includes(String(item.quantity).toLowerCase());
                              const isUnitMissing = !item.unit || ['none', 'null', 'missing', 'unknown'].includes(String(item.unit).toLowerCase());

                              if (isQtyMissing) {
                                return <span className="font-bold text-[9px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 mr-1.5 shrink-0">Missing Qty</span>;
                              }
                              return (
                                <span className="font-bold text-slate-900 mr-2 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded shrink-0">
                                  {item.quantity}{!isUnitMissing ? ` ${item.unit}` : 'x'}
                                </span>
                              );
                            })()}
                            <div className="truncate">
                              <span className="font-bold text-slate-900 block truncate" title={item.name}>{item.raw_name || item.name}</span>
                              {item.resolution_status === 'suggested' && item.canonical_name && (
                                <div className="mt-1 text-[10px] text-blue-650 font-bold flex flex-wrap items-center gap-1">
                                  <span className="bg-blue-50 border border-blue-200 px-1 rounded">Suggested: {item.canonical_name}</span>
                                  <span className="text-slate-500 font-normal ml-1">
                                    <button className="underline hover:text-blue-800 font-semibold cursor-pointer" onClick={(e) => { e.preventDefault(); handleResolveSuggestion(idx, 'accepted'); }}>Accept</button> |
                                    <button className="underline hover:text-blue-800 ml-1 cursor-pointer" onClick={(e) => { e.preventDefault(); handleResolveSuggestion(idx, 'kept_raw'); }}>Keep spoken</button>
                                  </span>
                                </div>
                              )}
                              {item.alias_used && item.canonical_name && (
                                <div className="mt-0.5 text-[9px] text-emerald-600 font-bold">
                                  Auto-applied alias: {item.canonical_name}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            {item.price !== undefined && item.price !== null && item.price > 0 ? (
                              <span className="font-mono text-slate-800 font-bold">
                                ₹{(item.price * item.quantity).toFixed(2)}
                              </span>
                            ) : (
                              <span className="text-slate-400 font-medium italic text-[10px]">Price pending</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    {(() => {
                      const orderTotal = selectedCard.items.reduce((sum, item) => sum + ((item.quantity || 0) * (item.price || 0)), 0);
                      const hasMissingPrice = selectedCard.items.some(item => item.price === undefined || item.price === null || item.price <= 0);
                      return (
                        <div className="mt-4 pt-3 border-t border-slate-100 flex justify-between items-center gap-2 text-sm font-semibold text-slate-600">
                          <span className="text-slate-500 text-xs uppercase tracking-wider font-bold">Calculated Grand Total</span>
                          <div className="flex flex-col items-end">
                            <span className="text-base sm:text-lg font-black text-slate-900 font-mono bg-slate-50 border border-slate-150 px-3 py-0.5 rounded-lg">
                              ₹{orderTotal.toFixed(2)}
                            </span>
                            {hasMissingPrice && (
                              <span className="text-[10px] text-amber-600 font-bold mt-1 text-right">
                                ⚠ Pending Verification
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

                  {/* Collapsible Transcript Section */}
                  {selectedCard.transcript && (
                    <div className="pt-4 border-t border-slate-100">
                      <button
                        type="button"
                        onClick={() => setIsAiAnalysisExpanded(!isAiAnalysisExpanded)}
                        className="w-full flex items-center justify-between text-[10px] font-bold text-slate-450 uppercase tracking-wider py-2 px-3 bg-white border border-slate-200 hover:bg-slate-50/50 hover:border-slate-300 rounded-lg transition-all"
                      >
                        <span>Original Transcript</span>
                        <svg
                          className={`h-3 w-3 transform transition-transform duration-200 text-slate-400 ${isAiAnalysisExpanded ? 'rotate-180' : ''
                            }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>

                      {isAiAnalysisExpanded && (
                        <div className="mt-3 p-4 bg-slate-50 border border-slate-150 rounded-lg space-y-4">
                          {/* Original AI Transcript */}
                          <div>
                            <blockquote className="text-xs text-slate-650 bg-white p-2.5 rounded border border-slate-200 italic leading-relaxed font-medium">
                              "{selectedCard.transcript}"
                            </blockquote>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-100 space-y-2">

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
                      className="flex-1 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-emerald-600 text-white rounded text-xs font-bold cursor-pointer transition-colors shadow-xs"
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
