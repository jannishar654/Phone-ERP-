import { ActionCard, Item } from '../types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

export async function transcribeAudio(audioFile: File): Promise<{ transcript: string; confidence: number | null }> {
  const formData = new FormData();
  formData.append('file', audioFile);

  const res = await fetch(`${API_BASE_URL}/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || 'Audio transcription failed');
  }

  return res.json();
}

export async function extractActionCard(transcript: string, source: 'audio' | 'text' = 'text'): Promise<ActionCard> {
  try {
    const res = await fetch(`${API_BASE_URL}/extract-action-card`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ transcript, source }),
    });
    if (!res.ok) throw new Error();
    return res.json();
  } catch (e) {
    // Generate রাহুল শর্মা mock card locally
    const dummyCard: ActionCard = {
      id: `ac_${Math.random().toString(36).substr(2, 9)}`,
      customer_name: "Rahul Sharma",
      customer_phone: "9876543210",
      items: [
        { name: "Milk (litres)", quantity: 5, price: 60.00 },
        { name: "Paneer", quantity: 2, price: 150.00 }
      ],
      delivery_address: "Sector 15, Noida",
      delivery_time: "Tomorrow Morning",
      status: "pending",
      source: source,
      transcript: transcript,
      created_at: new Date().toISOString()
    };
    const db = getLocalDB();
    db.unshift(dummyCard);
    setLocalDB(db);
    return dummyCard;
  }
}

export async function getActionCards(): Promise<ActionCard[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/action-cards`);
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
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}`);
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
    const res = await fetch(`${API_BASE_URL}/action-cards`, {
      method: 'POST',
      headers: {
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
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}`, {
      method: 'PUT',
      headers: {
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
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}/status`, {
      method: 'PATCH',
      headers: {
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

export async function deleteActionCard(cardId: string): Promise<void> {
  try {
    const res = await fetch(`${API_BASE_URL}/action-cards/${cardId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error();
  } catch (err) {
    const db = getLocalDB();
    const updated = db.filter(c => c.id !== cardId);
    setLocalDB(updated);
  }
}
