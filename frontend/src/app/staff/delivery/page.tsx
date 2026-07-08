'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { getStaffOrders, updateStaffOrderStatus, validateStaffToken, getMe } from '@/lib/api_access';

function DeliveryDashboard() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const router = useRouter();
  
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [logoutVisible, setLogoutVisible] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        if (token) {
          const val = await validateStaffToken(token);
          if (!val.valid || (val.role !== 'delivery' && val.role !== 'owner')) {
            setError('Invalid or expired token.');
            setLoading(false);
            return;
          }
        } else {
          try {
            const me = await getMe();
            if (me.role !== 'delivery' && me.role !== 'owner') {
              setError('Insufficient permissions.');
              setLoading(false);
              return;
            }
            setLogoutVisible(true);
          } catch (e) {
            setError('Please log in.');
            router.push('/login?redirectTo=/staff/delivery');
            return;
          }
        }
        
        const data = await getStaffOrders(token, 'delivery');
        setOrders(data);
      } catch (err) {
        setError('Failed to load delivery orders.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token, router]);

  const handleMarkDelivered = async (orderId: string) => {
    try {
      await updateStaffOrderStatus(token, orderId, 'delivered');
      setOrders(orders.filter(o => o.id !== orderId));
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
  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-8 flex flex-col items-center justify-center">
        <div className="bg-white p-8 rounded-xl shadow-sm text-center border border-slate-200">
          <p className="text-red-500 font-bold mb-4">{error}</p>
          <button onClick={() => router.push('/login')} className="px-4 py-2 bg-indigo-600 text-white rounded font-semibold text-sm">
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-6">
      <div className="flex justify-between items-end border-b pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Delivery Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Orders ready for delivery.</p>
        </div>
        <div className="flex items-center gap-4">
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

      {orders.length === 0 ? (
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
                
                {order.customer && (
                  <div className="text-sm text-slate-600 mb-4 p-3 bg-slate-50 rounded-lg">
                    <div className="font-semibold text-slate-800 mb-1">Customer Info:</div>
                    <div>{order.customer.name}</div>
                    {order.customer.phone && <div className="text-indigo-600">{order.customer.phone}</div>}
                  </div>
                )}
                
                <div className="text-sm text-slate-600 mb-4">
                  <div className="font-semibold text-slate-800 mb-1">Items:</div>
                  <ul className="list-disc pl-5 space-y-1">
                    {order.order_items?.map((item: any) => (
                      <li key={item.id}>
                        {item.quantity}x {item.display_name || item.raw_name}
                      </li>
                    ))}
                  </ul>
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
