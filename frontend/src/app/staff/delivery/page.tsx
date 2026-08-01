'use client';

import { Suspense, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { CalendarClock, MapPin, Phone, UserRound } from 'lucide-react';
import { getStaffOrders, updateStaffOrderStatus, validateStaffToken, getMe } from '@/lib/api_access';
import { formatDeliveryTime } from '@/lib/order_display';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { fulfillmentLabel, restaurantItemDetails } from '@/lib/restaurant_order';

function DeliveryDashboard() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const router = useRouter();
  
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [logoutVisible, setLogoutVisible] = useState(false);
  const { lastUpdated, refreshError, manualRefresh, silentRefresh } = useAutoRefresh(async (isSilent) => {
    try {
      if (!isSilent) {
        if (orders.length === 0) setLoading(true);
        if (token) {
          const val = await validateStaffToken(token);
          if (!val.valid || (val.role !== 'delivery' && val.role !== 'owner')) {
            setError('Invalid or expired token.');
            return;
          }
        } else {
          try {
            const me = await getMe();
            if (me.role !== 'delivery' && me.role !== 'owner') {
              setError('Insufficient permissions.');
              return;
            }
            setLogoutVisible(true);
          } catch (e) {
            setError('Please log in.');
            router.push('/login?redirectTo=/staff/delivery');
            return;
          }
        }
      }
      
      const data = await getStaffOrders(token, 'delivery');
      setOrders(data);
    } catch (err: any) {
      if (!isSilent && orders.length === 0) setError('Failed to load delivery orders.');
      else throw err;
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, 10000);

  const handleMarkDelivered = async (orderId: string) => {
    try {
      await updateStaffOrderStatus(token, orderId, 'delivered');
      setOrders(orders.filter(o => o.id !== orderId));
      silentRefresh();
    } catch (err) {
      alert('Failed to update order status');
    }
  };

  const handleLogout = async () => {
    const { authClient } = await import('@/lib/supabase/client');
    await authClient.signOut();
    router.replace('/login');
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading...</div>;

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-6">
      <div className="flex justify-between items-end border-b pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Delivery Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Orders ready for delivery.</p>
        </div>
        <div className="flex items-center gap-4">
          {refreshError && <span className="text-xs text-red-500 hidden sm:inline" title={refreshError}>Unable to refresh. Showing previously loaded data.</span>}
          {lastUpdated && !refreshError && <span className="text-xs text-slate-500 hidden sm:inline">Last updated: {lastUpdated.toLocaleTimeString()}</span>}
          <button onClick={manualRefresh} className="text-xs font-semibold px-3 py-1.5 bg-slate-100 text-slate-700 rounded hover:bg-slate-200 transition-colors">
            Refresh
          </button>
          <div className="bg-emerald-100 text-emerald-800 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide">
            Delivery Mode
          </div>
          {logoutVisible && (
            <button onClick={handleLogout} className="text-sm font-semibold text-slate-500 hover:text-slate-800">
              Log out
            </button>
          )}
        </div>
      </div>

      {error ? (
        <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-lg flex justify-between items-center">
          <span className="font-semibold">{error}</span>
          <button onClick={() => router.push('/login')} className="px-3 py-1.5 bg-red-600 text-white rounded text-sm font-bold hover:bg-red-700">
            Go to Login
          </button>
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-12 text-slate-500">No orders currently out for delivery.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {orders.map(order => (
            <div key={order.id} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-bold text-slate-900">Order #{order.order_number || order.id.slice(0, 8)}</h3>
                  <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full font-semibold">Out for Delivery</span>
                </div>
                
                {(order.customer || order.customer_name || order.customer_phone) && (
                  <div className="mb-4 space-y-2 bg-slate-50 p-3 text-sm text-slate-700 rounded-md">
                    <div className="font-semibold text-slate-800">Customer</div>
                    {(order.customer?.name || order.customer_name) && (
                      <div className="flex items-center gap-2">
                        <UserRound className="h-4 w-4 text-slate-500" aria-hidden="true" />
                        <span>{order.customer?.name || order.customer_name}</span>
                      </div>
                    )}
                    {(order.customer?.phone || order.customer_phone) && (
                      <div className="flex items-center gap-2 text-indigo-700">
                        <Phone className="h-4 w-4" aria-hidden="true" />
                        <span>{order.customer?.phone || order.customer_phone}</span>
                      </div>
                    )}
                  </div>
                )}
                
                <div className="text-sm text-slate-600 mb-4">
                  <div className="font-semibold text-slate-800 mb-1">Items:</div>
                  <ul className="list-disc pl-5 space-y-1">
                    {order.order_items?.map((item: any) => (
                      <li key={item.id}>
                        {item.quantity}{item.unit ? ` ${item.unit}` : ' ×'} {item.display_name || item.raw_name}
                        {restaurantItemDetails(item).length > 0 && (
                          <span className="block text-xs text-amber-700">{restaurantItemDetails(item).join(' · ')}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="mb-4 space-y-3 border-t border-slate-100 pt-3 text-sm text-slate-700">
                  <div className="flex items-start gap-2">
                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                    <div>
                      <p className="text-xs font-semibold uppercase text-slate-500">Delivery address</p>
                      <p className="mt-0.5">{order.delivery_address || 'Address not provided'}</p>
                    </div>
                  </div>
                  {order.delivery_time && (
                    <div className="flex items-start gap-2">
                      <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                      <div>
                        <p className="text-xs font-semibold uppercase text-slate-500">Scheduled</p>
                        <p className="mt-0.5">{formatDeliveryTime(order.delivery_time)}</p>
                      </div>
                    </div>
                  )}
                  {(fulfillmentLabel(order.fulfillment_type) || order.table_number || order.special_instructions) && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">
                      {fulfillmentLabel(order.fulfillment_type) && <p><span className="font-semibold">Fulfilment:</span> {fulfillmentLabel(order.fulfillment_type)}</p>}
                      {order.table_number && <p><span className="font-semibold">Table:</span> {order.table_number}</p>}
                      {order.special_instructions && <p><span className="font-semibold">Instructions:</span> {order.special_instructions}</p>}
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleMarkDelivered(order.id)}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold transition-colors mt-4 cursor-pointer"
              >
                Mark as Delivered
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DeliveryDashboardPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-500">Loading...</div>}>
      <DeliveryDashboard />
    </Suspense>
  );
}
