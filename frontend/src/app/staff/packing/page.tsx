'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { getStaffOrders, updateStaffOrderStatus, validateStaffToken } from '@/lib/api_access';

function PackingDashboard() {
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
        if (!val.valid || (val.role !== 'packer' && val.role !== 'owner')) {
          setError('Invalid or expired token.');
          setLoading(false);
          return;
        }
        
        const data = await getStaffOrders(token, 'packer');
        setOrders(data);
      } catch (err) {
        setError('Failed to load packing orders.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const handleMarkOutForDelivery = async (orderId: string) => {
    if (!token) return;
    try {
      await updateStaffOrderStatus(token, orderId, 'out_for_delivery');
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
          <h1 className="text-2xl font-extrabold text-slate-900">Packing Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Orders ready to be packed.</p>
        </div>
        <div className="bg-indigo-100 text-indigo-800 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide">
          Packer Mode
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="text-center py-12 text-slate-500">No orders currently in packing stage.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {orders.map(order => (
            <div key={order.id} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-bold text-slate-900">Order #{order.orderNumber || order.id.slice(0, 8)}</h3>
                  <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded-full font-semibold">Packing</span>
                </div>
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
                onClick={() => handleMarkOutForDelivery(order.id)}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold transition-colors mt-4"
              >
                Mark Out for Delivery
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PackingDashboardPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-500">Loading Suspense...</div>}>
      <PackingDashboard />
    </Suspense>
  );
}
