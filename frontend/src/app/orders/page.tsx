"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getOrders, updateOrderLifecycleStatus } from "@/lib/api";

interface OrderItem {
  id: string;
  raw_name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  line_total: number;
}

interface Order {
  id: string;
  total_amount: number;
  status: string;
  lifecycle_status: string | null;
  created_at: string;
  order_items: OrderItem[];
  orderNumber?: number;
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<string>("packing");
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const data = await getOrders();
      setOrders(data || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (orderId: string, newStatus: string) => {
    try {
      setUpdating(orderId);
      const updated = await updateOrderLifecycleStatus(orderId, newStatus);
      setOrders(orders.map(o => o.id === orderId ? { ...o, lifecycle_status: updated.lifecycle_status } : o));
    } catch (err: any) {
      alert(`Failed to update: ${err.message}`);
    } finally {
      setUpdating(null);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading orders...</div>;

  const getStatusCategory = (lifecycle: string | null) => {
    if (!lifecycle || lifecycle === 'pending_review' || lifecycle === 'packing') return 'packing';
    return lifecycle;
  };

  const filteredOrders = orders.filter(o => getStatusCategory(o.lifecycle_status) === activeTab);

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <header className="bg-white border-b px-4 py-3 sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="p-2 -ml-2 rounded-full hover:bg-gray-100 text-gray-600 transition-colors text-sm font-bold">
            &larr; Back
          </Link>
          <h1 className="text-lg font-semibold text-gray-900">Final Orders / Bills</h1>
        </div>
      </header>

      <main className="p-4 max-w-lg mx-auto">
        {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">{error}</div>}

        <div className="flex gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide">
          {['packing', 'out_for_delivery', 'delivered', 'cancelled'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap ${
                activeTab === tab 
                  ? 'bg-indigo-600 text-white' 
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              {tab.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
            </button>
          ))}
        </div>

        <div className="space-y-4">
          {filteredOrders.length === 0 ? (
            <p className="text-gray-500 text-center mt-10">No orders in this status.</p>
          ) : (
            filteredOrders.map(order => (
              <div key={order.id} className="bg-white p-4 rounded-xl shadow-sm border">
                <div className="flex justify-between items-start mb-3 border-b pb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">Order #{order.orderNumber ?? order.id.slice(0, 8)}</h3>
                    <p className="text-xs text-gray-500">{new Date(order.created_at).toLocaleString()}</p>
                  </div>
                  <div className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1
                    ${order.lifecycle_status === 'delivered' ? 'bg-green-100 text-green-700' : 
                      order.lifecycle_status === 'cancelled' ? 'bg-red-100 text-red-700' :
                      'bg-indigo-100 text-indigo-700'}`}>
                    {order.lifecycle_status === 'delivered' ? '✅' : '📦'}
                    {order.lifecycle_status || order.status}
                  </div>
                </div>

                <div className="space-y-2 mb-3">
                  {order.order_items && order.order_items.map(item => (
                    <div key={item.id} className="flex justify-between text-sm">
                      <span className="text-gray-700">{item.raw_name} <span className="text-gray-400">x {item.quantity} {item.unit}</span></span>
                      <span className="font-medium">₹{item.line_total}</span>
                    </div>
                  ))}
                </div>

                <div className="flex justify-between items-center border-t pt-3 font-semibold mb-4">
                  <span>Total</span>
                  <span>₹{order.total_amount}</span>
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  {getStatusCategory(order.lifecycle_status) === 'packing' && (
                    <>
                      <button 
                        onClick={() => handleUpdateStatus(order.id, 'out_for_delivery')}
                        disabled={updating === order.id}
                        className="flex-1 bg-indigo-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
                      >
                        Mark Out for Delivery
                      </button>
                      <button 
                        onClick={() => handleUpdateStatus(order.id, 'cancelled')}
                        disabled={updating === order.id}
                        className="px-4 bg-gray-100 text-gray-700 py-2 rounded-lg text-sm font-semibold hover:bg-gray-200 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                  {getStatusCategory(order.lifecycle_status) === 'out_for_delivery' && (
                    <>
                      <button 
                        onClick={() => handleUpdateStatus(order.id, 'delivered')}
                        disabled={updating === order.id}
                        className="flex-1 bg-green-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-green-700 disabled:opacity-50"
                      >
                        Mark Delivered
                      </button>
                      <button 
                        onClick={() => handleUpdateStatus(order.id, 'cancelled')}
                        disabled={updating === order.id}
                        className="px-4 bg-gray-100 text-gray-700 py-2 rounded-lg text-sm font-semibold hover:bg-gray-200 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
