import { ActionCard, Item } from '../types';
import { supabase } from './supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (!supabase) return {};
  const { data } = await supabase.auth.getSession();
  if (data?.session?.access_token) {
    return { 'Authorization': `Bearer ${data.session.access_token}` };
  }
  return {};
}

const INITIAL_LOCAL_DB: ActionCard[] = [
  {
    id: "ac_01h9b82c",
    customer_name: "Johnathan Archer",
    customer_phone: "+1 310-555-2150",
    items: [
      { name: "Plasma Injector Model D", quantity: 2, price: 450.00 },
      { name: "Dilithium Crystal Shards (Grade A)", quantity: 5, price: 1200.00 }
    ],
    delivery_address: "Warp Nacelle Bay, Dock 4, Starbase 1",
    delivery_time: "Stardate 58432.1 (Friday morning)",
    status: "pending",
    source: "audio",
    transcript: "Yeah, this is Captain Archer. We need two of those Plasma Injectors, model D, and five grade-A dilithium crystal shards delivered to Dock 4 at Starbase 1 by Friday morning. Charge it to Starfleet Command.",
    created_at: new Date().toISOString()
  },
  {
    id: "ac_01h9b83f",
    customer_name: "Ellen Ripley",
    customer_phone: "+1 800-555-8299",
    items: [
      { name: "M41A Pulse Rifle", quantity: 4, price: 899.99 },
      { name: "Incendiary Ammo Crates", quantity: 2, price: 150.00 }
    ],
    delivery_address: "USS Sulaco Cargo Bay 2",
    delivery_time: "ASAP before launch",
    status: "processing",
    source: "audio",
    transcript: "This is Ripley, Nostromo officer. We need immediate delivery of four M41A Pulse Rifles and two crates of incendiary ammunition. Send it straight to Cargo Bay 2 on the Sulaco. Hurry up, we are running out of time.",
    created_at: new Date().toISOString()
  },
  {
    id: "ac_01h9b84g",
    customer_name: "Arthur Dent",
    customer_phone: "+44 20-7946-0922",
    items: [
      { name: "Electronic Towel (Microfiber)", quantity: 1, price: 42.00 },
      { name: "Nutri-Matic Tea Dispenser", quantity: 1, price: 120.00 }
    ],
    delivery_address: "Megadodo Publications, Islington, London",
    delivery_time: "Next Thursday morning",
    status: "completed",
    source: "text",
    transcript: "I'd like to place an order for one microfiber electronic towel and one Nutri-Matic tea dispenser. Delivery address is Megadodo Publications in London. Needs to arrive next Thursday, because they are demolishing my house next Thursday.",
    created_at: new Date().toISOString()
  }
];

function getLocalDB(): ActionCard[] {
  if (typeof window === 'undefined') return INITIAL_LOCAL_DB;
  const data = localStorage.getItem('phoneerp_cards_db');
  if (!data) {
    localStorage.setItem('phoneerp_cards_db', JSON.stringify(INITIAL_LOCAL_DB));
    return INITIAL_LOCAL_DB;
  }
  return JSON.parse(data);
}

function setLocalDB(db: ActionCard[]) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('phoneerp_cards_db', JSON.stringify(db));
}

export async function getHealth(): Promise<{ status: string; timestamp: string; service: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) throw new Error('Failed to fetch API health status');
    return res.json();
  } catch (e) {
    return { status: 'healthy (offline-mode)', timestamp: new Date().toISOString(), service: 'PhoneERP Mock DB' };
  }
}

export async function transcribeAudio(audioFile: File, provider: string = "gemini"): Promise<{ transcript: string; confidence: number | null }> {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('provider', provider); // Send as Form Data

  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/transcribe?provider=${provider}`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Audio transcription failed');
  }

  return res.json();
}

export async function extractActionCardFromAudio(
  audioFile: File,
  pipeline: string = "gemini_audio_extraction"
): Promise<ActionCard> {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('pipeline', pipeline);

  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/extract-action-card-audio`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to extract order details from audio.');
  }

  return res.json();
}

export async function extractActionCard(
  transcript: string, 
  source: 'audio' | 'text' = 'text',
  provider: string = "gemini",
  stt_provider: string | null = null,
  pipeline: string = "gemini_gemini",
  save_evaluation: boolean = false
): Promise<ActionCard> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/extract-action-card`, {
    method: 'POST',
    headers: {
      ...headers,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ transcript, source, provider, stt_provider, pipeline, save_evaluation }),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to extract order details.');
  }
  return res.json();
}

export async function getActionCards(): Promise<ActionCard[]> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/action-cards`, { headers });
    if (!res.ok) throw new Error();
    const data = await res.json();
    setLocalDB(data);
    return data;
  } catch (err) {
    return getLocalDB();
  }
}

export async function getActionCard(cardId: string): Promise<ActionCard> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}`, { headers });
    if (!res.ok) throw new Error();
    return res.json();
  } catch (err) {
    const db = getLocalDB();
    const card = db.find(c => c.id === cardId);
    if (!card) throw new Error(`ActionCard with ID ${cardId} not found`);
    return card;
  }
}

export async function createActionCard(cardData: Partial<ActionCard>): Promise<ActionCard> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/action-cards`, {
      method: 'POST',
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cardData),
    });
    if (!res.ok) throw new Error();
    return res.json();
  } catch (err) {
    const db = getLocalDB();
    const newCard: ActionCard = {
      id: cardData.id || `ac_${Math.random().toString(36).substr(2, 9)}`,
      customer_name: cardData.customer_name || '',
      customer_phone: cardData.customer_phone || '',
      items: (cardData.items || []) as Item[],
      delivery_address: cardData.delivery_address || '',
      delivery_time: cardData.delivery_time || '',
      status: cardData.status || 'pending',
      source: cardData.source || 'text',
      transcript: cardData.transcript || 'Manual order entry',
      created_at: new Date().toISOString()
    };
    db.unshift(newCard);
    setLocalDB(db);
    return newCard;
  }
}

export async function updateActionCard(cardId: string, cardData: Partial<ActionCard>): Promise<ActionCard> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}`, {
      method: 'PUT',
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cardData),
    });
    if (!res.ok) throw new Error();
    return res.json();
  } catch (err) {
    const db = getLocalDB();
    const idx = db.findIndex(c => c.id === cardId);
    if (idx !== -1) {
      db[idx] = { ...db[idx], ...cardData };
      setLocalDB(db);
      return db[idx];
    }
    throw new Error('Card not found');
  }
}

export async function updateActionCardStatus(cardId: string, status: string): Promise<ActionCard> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}/status`, {
      method: 'PATCH',
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error();
    return res.json();
  } catch (err) {
    const db = getLocalDB();
    const idx = db.findIndex(c => c.id === cardId);
    if (idx !== -1) {
      db[idx].status = status;
      setLocalDB(db);
      return db[idx];
    }
    throw new Error('Card not found');
  }
}

export async function convertActionCardToOrder(cardId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/orders/action-cards/${cardId}/convert`, {
    method: 'POST',
    headers,
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to convert action card to order.');
  }
  return res.json();
}

export async function deleteActionCard(cardId: string): Promise<void> {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}`, {
      method: 'DELETE',
      headers,
    });
    if (!res.ok) throw new Error();
  } catch (err) {
    const db = getLocalDB();
    const updated = db.filter(c => c.id !== cardId);
    setLocalDB(updated);
  }
}

// Catalog API
export async function getCatalogItems(): Promise<any[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/catalog/`, { headers });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to fetch catalog items.');
  }
  return res.json();
}

export async function createCatalogItem(itemData: any): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/catalog/`, {
    method: 'POST',
    headers: {
      ...headers,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(itemData),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to create catalog item.');
  }
  return res.json();
}

export async function updateCatalogItemStatus(itemId: string, updates: any): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/catalog/${itemId}`, {
    method: 'PUT',
    headers: {
      ...headers,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to update catalog item.');
  }
  return res.json();
}

export async function getOrders(): Promise<any[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/orders/`, { headers });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Failed to fetch orders.');
  }
  return res.json();
}
