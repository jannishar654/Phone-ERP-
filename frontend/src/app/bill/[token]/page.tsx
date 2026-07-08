'use client';

import { useState, useEffect } from 'react';
import { getPublicBill } from '@/lib/api_access';

export default function PublicBillPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const billData = await getPublicBill(params.token);
        setData(billData);
      } catch (err) {
        setError('Invalid or expired bill link.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [params.token]);

  if (loading) return <div className="p-8 text-center text-slate-500">Loading your bill...</div>;
  if (error) return <div className="p-8 text-center text-red-500 font-bold">{error}</div>;

  const { order, shop_info } = data;

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6 lg:p-8 space-y-8 bg-slate-50 min-h-screen">
      <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-10 shadow-sm">
        <div className="flex justify-between items-start border-b border-slate-100 pb-6 mb-6">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">{shop_info?.name || 'Store Bill'}</h1>
            <p className="text-sm text-slate-500 mt-1">Receipt for your order</p>
          </div>
          <div className="text-right">
            <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide border ${
              order.lifecycle_status === 'delivered' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' :
              order.lifecycle_status === 'out_for_delivery' ? 'bg-indigo-100 text-indigo-800 border-indigo-200' :
              order.lifecycle_status === 'cancelled' ? 'bg-red-100 text-red-800 border-red-200' :
              'bg-amber-100 text-amber-800 border-amber-200'
            }`}>
              {order.lifecycle_status ? order.lifecycle_status.replace('_', ' ') : 'Pending'}
            </span>
            <div className="text-sm font-semibold text-slate-700 mt-2">Order #{order.orderNumber || order.id.slice(0, 8)}</div>
          </div>
        </div>

        <div className="mb-8">
          <h2 className="text-lg font-bold text-slate-900 mb-4">Order Items</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-left">
              <thead>
                <tr className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-2 px-1">Item</th>
                  <th className="py-2 px-1 text-right">Qty</th>
                  <th className="py-2 px-1 text-right">Price</th>
                  <th className="py-2 px-1 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {order.order_items?.map((item: any) => (
                  <tr key={item.id}>
                    <td className="py-3 px-1">{item.display_name || item.raw_name}</td>
                    <td className="py-3 px-1 text-right">{item.quantity} {item.unit || ''}</td>
                    <td className="py-3 px-1 text-right">₹{item.unit_price?.toFixed(2) || '0.00'}</td>
                    <td className="py-3 px-1 text-right font-semibold text-slate-900">₹{item.line_total?.toFixed(2) || '0.00'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-6 flex flex-col sm:flex-row justify-between gap-6">
          <div className="text-sm text-slate-600 space-y-1">
            <div className="font-semibold text-slate-800 mb-2">Delivery Details</div>
            {order.delivery_address && <div><span className="font-medium text-slate-700">Address:</span> {order.delivery_address}</div>}
            {order.delivery_time && <div><span className="font-medium text-slate-700">Time:</span> {order.delivery_time}</div>}
          </div>
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 sm:w-1/3 flex flex-col justify-center items-end">
            <div className="text-sm text-slate-500 mb-1 font-semibold uppercase tracking-wide">Total Amount</div>
            <div className="text-3xl font-extrabold text-slate-900">₹{order.total_amount?.toFixed(2) || '0.00'}</div>
          </div>
        </div>
      </div>
      <div className="text-center text-xs text-slate-400">
        Thank you for shopping with {shop_info?.name || 'us'}.
      </div>
    </div>
  );
}
