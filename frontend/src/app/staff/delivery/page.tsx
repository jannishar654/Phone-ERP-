'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { getStaffOrders, updateStaffOrderStatus, validateStaffToken } from '@/lib/api_access';

function DeliveryDashboard() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      if (!token) {
        setError('No access token provided.');
        setLoading(false);
        return;
      }
      try {
        const val = await validateStaffToken(token);
        if (!val.valid || (val.role !== 'delivery' && val.role !== 'owner')) {
          setError('Invalid or expired token.');
          setLoading(false);
          return;
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
  }, [token]);

  const handleMarkDelivered = async (orderId: string) => {
    if (!token) return;
    try {
      await updateStaffOrderStatus(token, orderId, 'delivered');
      setOrders(orders.filter(o => o.id !== orderId));
    } catch (err) {
      alert('Failed to update order status');
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading...</div>;
  if (error) return <div className="p-8 text-center text-red-500 font-bold">{error}</div>;

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-6">
      <div className="flex justify-between items-end border-b pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Delivery Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Orders out for delivery.</p>
        </div>
        <div className="bg-emerald-100 text-emerald-800 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide">
          Delivery Mode
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
                  <h3 className="font-bold text-slate-900">Order #{order.orderNumber || order.id.slice(0, 8)}</h3>
                  <span className="text-xs bg-indigo-100 text-indigo-800 px-2 py-1 rounded-full font-semibold">Out for Delivery</span>
                </div>
                <div className="text-sm text-slate-600 mb-4 space-y-2">
                  <div>
                    <span className="font-semibold text-slate-800">Address:</span> {order.delivery_address || 'Not specified'}
                  </div>
                  {order.delivery_time && (
                    <div>
                      <span className="font-semibold text-slate-800">Time:</span> {order.delivery_time}
                    </div>
                  )}
                  <div>
                    <span className="font-semibold text-slate-800">Total:</span> ₹{order.total_amount?.toFixed(2) || '0.00'}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleMarkDelivered(order.id)}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold transition-colors mt-4"
              >
                Mark Delivered
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
    <Suspense fallback={<div className="p-8 text-center text-slate-500">Loading Suspense...</div>}>
      <DeliveryDashboard />
    </Suspense>
  );
}
