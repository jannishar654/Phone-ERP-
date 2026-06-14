export interface Item {
  name: string;
  unit?: string;
  quantity: number;
  price?: number;
}

export type ActionCardStatus = 'pending' | 'processing' | 'completed';

export interface ActionCard {
  id: string;
  customer_name?: string;
  customer_phone?: string;
  items: Item[];
  delivery_address?: string;
  delivery_time?: string;
  status: ActionCardStatus | string;
  source: 'audio' | 'text' | string;
  transcript: string;
  created_at: string; // ISO datetime string
}
