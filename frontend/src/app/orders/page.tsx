"use client";

import { useState } from "react";
import Link from "next/link";
import { getOrders, updateOrderLifecycleStatus } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";

interface OrderItem {
  id: string;
  raw_name: string;
  display_name?: string;
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

  const { lastUpdated, refreshError, manualRefresh, silentRefresh } = useAutoRefresh(async (isSilent) => {
    try {
      if (!isSilent && orders.length === 0) setLoading(true);
      const data = await getOrders();
      setOrders(data || []);
    } catch (err: unknown) {
      if (!isSilent && orders.length === 0) {
        setError(err instanceof Error ? err.message : 'Failed to load orders.');
      }
      else throw err;
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, 10000);

  const handleUpdateStatus = async (orderId: string, newStatus: string) => {
    try {
      setUpdating(orderId);
      const updated = await updateOrderLifecycleStatus(orderId, newStatus);
      setOrders((currentOrders) => currentOrders.map((order) => (
        order.id === orderId ? { ...order, lifecycle_status: updated.lifecycle_status } : order
      )));
      silentRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update the order.');
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
    <div className="mx-auto w-full max-w-5xl pb-16">
      <header className="mb-5 flex flex-col gap-4 border-b border-slate-200 bg-white/80 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:rounded-lg sm:border">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <Link href="/dashboard" className="p-2 -ml-2 rounded-full hover:bg-gray-100 text-gray-600 transition-colors text-sm font-bold">
            &larr; Back
          </Link>
          <h1 className="truncate text-lg font-semibold text-gray-900">Final Orders / Bills</h1>
        </div>
        <div className="flex shrink-0 items-center gap-3 self-end sm:self-auto">
          {refreshError && <span className="text-xs text-red-500 hidden sm:inline" title={refreshError}>Unable to refresh. Showing previously loaded data.</span>}
          {lastUpdated && !refreshError && <span className="text-xs text-gray-500 hidden sm:inline">Last updated: {lastUpdated.toLocaleTimeString()}</span>}
          <button onClick={manualRefresh} className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 font-semibold rounded hover:bg-gray-200 transition-colors">
            Refresh
          </button>
        </div>
      </header>

      <main className="px-0 sm:px-2">
        {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">{error}</div>}

        <div className="mb-6 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          {['packing', 'out_for_delivery', 'delivered', 'cancelled'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`min-w-0 px-3 py-2.5 rounded-lg text-sm font-semibold sm:px-4 ${
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
              <article key={order.id} className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
                <div className="mb-3 flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-semibold text-gray-900">Order #{order.orderNumber ?? order.id.slice(0, 8)}</h3>
                    <p className="text-xs text-gray-500">{new Date(order.created_at).toLocaleString()}</p>
                  </div>
                  <div className={`flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs font-medium
                    ${order.lifecycle_status === 'delivered' ? 'bg-green-100 text-green-700' : 
                      order.lifecycle_status === 'cancelled' ? 'bg-red-100 text-red-700' :
                      'bg-indigo-100 text-indigo-700'}`}>
                    {order.lifecycle_status === 'delivered' ? '✅' : '📦'}
                    {order.lifecycle_status || order.status}
                  </div>
                </div>

                <div className="space-y-2 mb-3">
                  {order.order_items && order.order_items.map(item => (
                    <div key={item.id} className="flex min-w-0 justify-between gap-4 text-sm">
                      <span className="min-w-0 break-words text-gray-700">{item.display_name || item.raw_name} <span className="text-gray-400">x {item.quantity} {item.unit}</span></span>
                      <span className="shrink-0 font-medium">₹{item.line_total}</span>
                    </div>
                  ))}
                </div>

                <div className="flex justify-between items-center border-t pt-3 font-semibold mb-4">
                  <span>Total</span>
                  <span>₹{order.total_amount}</span>
                </div>

                {/* Actions */}
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
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
              </article>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
