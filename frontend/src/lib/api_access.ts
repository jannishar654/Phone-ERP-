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

// Access API
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
  const res = await fetch(`${API_BASE_URL}/access/staff`, { headers });
  if (!res.ok) throw new Error('Failed to fetch staff access');
  return res.json();
}

export async function revokeStaffAccess(id: string): Promise<any> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/access/staff/${id}/revoke`, { method: 'POST', headers });
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

export async function getStaffOrders(token: string, role: string): Promise<any[]> {
  const endpoint = role === 'packer' ? 'packing' : 'delivery';
  const res = await fetch(`${API_BASE_URL}/staff/orders/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
  if (!res.ok) throw new Error('Failed to fetch staff orders');
  return res.json();
}

export async function updateStaffOrderStatus(token: string, orderId: string, lifecycle_status: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/staff/orders/${orderId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, lifecycle_status })
  });
  if (!res.ok) throw new Error('Failed to update staff order status');
  return res.json();
}

// Public API
export async function getPublicBill(token: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/public/bill/${token}`);
  if (!res.ok) throw new Error('Failed to fetch public bill');
  return res.json();
}
