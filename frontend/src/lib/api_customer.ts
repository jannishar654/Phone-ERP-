const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const SESSION_KEY = 'phoneerp_customer_session';

export class CustomerApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'CustomerApiError';
  }
}

export type CustomerOrderItem = {
  id: string;
  display_name?: string;
  raw_name: string;
  quantity: number;
  unit?: string;
  unit_price: number;
  line_total: number;
};

export type CustomerOrderEvent = {
  lifecycle_status: string;
  occurred_at: string;
};

export type CustomerOrder = {
  id: string;
  record_type: 'order' | 'action_card';
  order_number?: number;
  total_amount: number;
  lifecycle_status: string;
  delivery_address?: string;
  delivery_time?: string;
  created_at: string;
  updated_at: string;
  packed_at?: string;
  out_for_delivery_at?: string;
  delivered_at?: string;
  cancelled_at?: string;
  items: CustomerOrderItem[];
  events: CustomerOrderEvent[];
};

export type CustomerOverview = {
  customer_name: string;
  shop_name: string;
  orders: CustomerOrder[];
};

function portalHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? sessionStorage.getItem(SESSION_KEY) : null;
  return token ? { 'X-Customer-Session': token } : {};
}

async function parseError(response: Response, fallback: string): Promise<CustomerApiError> {
  const payload = await response.json().catch(() => ({}));
  return new CustomerApiError(payload.detail || fallback, response.status);
}

export async function exchangeCustomerLink(token: string) {
  const response = await fetch(`${API_BASE_URL}/customer/access/exchange`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
    cache: 'no-store',
  });
  if (!response.ok) throw await parseError(response, 'Unable to open customer portal');
  const data = await response.json();
  sessionStorage.setItem(SESSION_KEY, data.session_token);
  return data;
}

export function hasCustomerSession() {
  return typeof window !== 'undefined' && Boolean(sessionStorage.getItem(SESSION_KEY));
}

export async function logoutCustomer() {
  await fetch(`${API_BASE_URL}/customer/access/logout`, {
    method: 'POST',
    headers: portalHeaders(),
  }).catch(() => undefined);
  sessionStorage.removeItem(SESSION_KEY);
}

export async function getCustomerOrders(): Promise<CustomerOverview> {
  const response = await fetch(`${API_BASE_URL}/customer/orders`, {
    headers: portalHeaders(),
    cache: 'no-store',
  });
  if (!response.ok) throw await parseError(response, 'Unable to load orders');
  return response.json();
}

export async function getCustomerBillUrl(orderId: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/customer/orders/${orderId}/bill`, {
    method: 'POST',
    headers: portalHeaders(),
  });
  if (!response.ok) throw await parseError(response, 'Unable to open bill');
  const data = await response.json();
  return data.bill_url;
}

export async function createCustomerOrderRequest(
  orderId: string,
  requestType: 'repeat_order' | 'cancel_order' | 'change_order',
  message?: string,
) {
  const response = await fetch(`${API_BASE_URL}/customer/orders/${orderId}/requests`, {
    method: 'POST',
    headers: { ...portalHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_type: requestType, message, payload: {} }),
  });
  if (!response.ok) throw await parseError(response, 'Unable to submit request');
  return response.json();
}

export async function createCustomerSupportRequest(message: string) {
  const response = await fetch(`${API_BASE_URL}/customer/support`, {
    method: 'POST',
    headers: { ...portalHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_type: 'support', message, payload: {} }),
  });
  if (!response.ok) throw await parseError(response, 'Unable to submit support request');
  return response.json();
}

export async function askCustomerAssistant(message: string) {
  const response = await fetch(`${API_BASE_URL}/customer/assistant`, {
    method: 'POST',
    headers: { ...portalHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) throw await parseError(response, 'Assistant is temporarily unavailable');
  return response.json();
}
