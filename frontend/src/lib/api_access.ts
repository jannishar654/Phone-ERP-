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

export interface WhatsAppConnectionStatus {
  embedded_signup_enabled: boolean;
  configured: boolean;
  status: 'not_connected' | 'pending' | 'active' | 'reconnect_required' | 'disconnected' | 'error';
  display_phone_number?: string | null;
  verified_name?: string | null;
  waba_id?: string | null;
  phone_number_id?: string | null;
  last_webhook_at?: string | null;
  last_health_check_at?: string | null;
  last_error?: string | null;
  connected_at?: string | null;
  token_expires_at?: string | null;
}

export interface WhatsAppOnboardingSession {
  state: string;
  app_id: string;
  configuration_id: string;
  graph_api_version: string;
  expires_in_seconds: number;
}

async function integrationError(res: Response, fallback: string): Promise<Error> {
  const payload = await res.json().catch(() => ({}));
  return new Error(payload.detail || fallback);
}

export async function getWhatsAppConnectionStatus(): Promise<WhatsAppConnectionStatus> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/integrations/whatsapp/status`, {
    headers,
    cache: 'no-store',
  });
  if (!res.ok) throw await integrationError(res, 'Failed to load WhatsApp connection');
  return res.json();
}

export async function createWhatsAppOnboardingSession(): Promise<WhatsAppOnboardingSession> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/integrations/whatsapp/onboarding-session`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw await integrationError(res, 'Failed to start WhatsApp connection');
  return res.json();
}

export async function completeWhatsAppOnboarding(data: {
  state: string;
  code: string;
  waba_id?: string;
  phone_number_id?: string;
  registration_pin: string;
}): Promise<WhatsAppConnectionStatus> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/integrations/whatsapp/callback`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await integrationError(res, 'Failed to complete WhatsApp connection');
  return res.json();
}

export async function checkWhatsAppConnection(): Promise<{
  healthy: boolean;
  status: string;
  display_phone_number?: string;
  verified_name?: string;
}> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/integrations/whatsapp/health-check`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw await integrationError(res, 'WhatsApp connection check failed');
  return res.json();
}

export async function disconnectWhatsApp(): Promise<void> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/integrations/whatsapp/connection`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) throw await integrationError(res, 'Failed to disconnect WhatsApp');
}

// Auth API
export async function getMe(): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/auth/me`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error('Failed to fetch user profile');
  return res.json();
}

export async function registerStaff(inviteCode: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/auth/register-staff`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ invite_code: inviteCode })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to register staff');
  }
  return res.json();
}

// Invites API
export async function createStaffInvite(shopId: string, role: string, label: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/invites/staff`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ shop_id: shopId, role, label, expires_in_days: 7 })
  });
  if (!res.ok) throw new Error('Failed to create staff invite');
  return res.json();
}

export async function listStaffInvites(): Promise<any[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/invites/staff`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error('Failed to fetch staff invites');
  return res.json();
}

export async function revokeStaffInvite(id: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/invites/staff/${id}/revoke`, { method: 'POST', headers, cache: "no-store" });
  if (!res.ok) throw new Error('Failed to revoke staff invite');
  return res.json();
}

// Access API (Legacy tokens)
export async function createStaffAccess(shopId: string, role: string, label: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/access/staff`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ shop_id: shopId, role, label, expires_in_days: 7 })
  });
  if (!res.ok) throw new Error('Failed to create staff access');
  return res.json();
}

export async function listStaffAccess(): Promise<any[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/access/staff`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error('Failed to fetch staff access');
  return res.json();
}

export async function revokeStaffAccess(id: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/access/staff/${id}/revoke`, { method: 'POST', headers, cache: "no-store" });
  if (!res.ok) throw new Error('Failed to revoke staff access');
  return res.json();
}

export async function createCustomerBillLink(orderId: string, shopId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/access/customer/${orderId}`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ order_id: orderId, shop_id: shopId, expires_in_days: 30 })
  });
  if (!res.ok) throw new Error('Failed to create customer link');
  return res.json();
}

// Staff APIs
export async function validateStaffToken(token: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/staff/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
  if (!res.ok) throw new Error('Failed to validate token');
  return res.json();
}

export async function getStaffOrders(token: string | null, role: string): Promise<any[]> {
  const headers = await getAuthHeaders();
  const endpoint = role === 'packer' ? 'packing' : 'delivery';
  const body: any = {};
  if (token) body.token = token;
  const res = await fetch(`${API_BASE_URL}/staff/orders/${endpoint}`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error('Failed to fetch staff orders');
  return res.json();
}

export async function updateStaffOrderStatus(token: string | null, orderId: string, lifecycle_status: string): Promise<any> {
  const headers = await getAuthHeaders();
  const body: any = { lifecycle_status };
  if (token) body.token = token;
  const res = await fetch(`${API_BASE_URL}/staff/orders/${orderId}/status`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error('Failed to update staff order status');
  return res.json();
}

// Public API
export async function getPublicBill(token: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/public/bill/${token}`, {
    cache: 'no-store'
  });
  if (!res.ok) throw new Error('Failed to fetch public bill');
  return res.json();
}

export async function listCustomerRequests(status: string = 'pending'): Promise<any[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/customer-requests?status=${encodeURIComponent(status)}`, {
    headers,
    cache: 'no-store',
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const requestId = payload.request_id ? ` (reference: ${payload.request_id})` : '';
    throw new Error(`${payload.detail || 'Failed to fetch customer requests'}${requestId}`);
  }
  return res.json();
}

export async function decideCustomerRequest(
  requestId: string,
  status: 'approved' | 'rejected' | 'resolved',
  ownerNote?: string,
): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/customer-requests/${requestId}`, {
    method: 'PATCH',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, owner_note: ownerNote || null }),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || 'Failed to update customer request');
  }
  return res.json();
}

export type OwnerNotification = {
  id: string;
  notification_type: 'new_order' | 'order_reminder' | 'customer_request';
  title: string;
  message: string;
  scheduled_at: string;
  action_card_id?: string;
  customer_request_id?: string;
};

export async function listOwnerNotifications(): Promise<OwnerNotification[]> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/owner-notifications`, {
    headers,
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch owner notifications');
  return res.json();
}

export async function acknowledgeOwnerNotification(notificationId: string): Promise<void> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/owner-notifications/${notificationId}/ack`, {
    method: 'POST',
    headers,
  });
  if (!res.ok && res.status !== 404) throw new Error('Failed to acknowledge notification');
}
