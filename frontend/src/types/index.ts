export interface Item {
  name: string;
  unit?: string;
  quantity: number;
  price?: number;
  raw_name?: string;
  canonical_name?: string;
  resolution_status?: string;
  resolution_source?: string;
  possible_matches?: string[];
  resolution_confidence?: number;
  alias_used?: boolean;
}

export type ActionCardStatus = 'pending' | 'processing' | 'completed';

export interface ActionCard {
  id: string;
  customer_name?: string;
  customer_phone?: string;
  items: Item[];
  delivery_address?: string;
  delivery_time?: string;
  delivery_time_raw?: string;
  delivery_time_normalized?: string;
  delivery_time_confidence?: number;
  delivery_time_warning?: string;
  delivery_address_raw?: string;
  risk_flags?: string[];
  missing_fields?: string[];
  validation_warnings?: string[];
  payment_method?: string;
  status: ActionCardStatus | string;
  source: 'audio' | 'text' | string;
  message_type?: string;
  confidence?: number;
  confidence_score?: number;
  confidence_label?: string;
  confidence_reasons?: string[];
  stt_provider?: string;
  extraction_provider?: string;
  metadata?: Record<string, any>;
  transcript: string;
  created_at: string; // ISO datetime string
}
