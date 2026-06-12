'use client';

import { useEffect, useState } from 'react';
import Link from 'next/navigation'; // Wait, let's make sure it imports from next/link
import LinkComponent from 'next/link';
import { getActionCards, deleteActionCard } from '@/lib/api';
import { ActionCard } from '@/types';

export default function OrdersList() {
  const [orders, setOrders] = useState<ActionCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search and Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'approved' | 'processing' | 'delivered' | 'rejected'>('all');

  const loadOrders = async () => {
    try {
      const data = await getActionCards();
      setOrders(data);
    } catch (err: any) {
      setError('Failed to load orders from backend.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, []);

  const handleDelete = async (orderId: string) => {
    if (window.confirm("Are you sure you want to delete this order?")) {
      try {
        await deleteActionCard(orderId);
        setOrders((prev) => prev.filter(o => o.id !== orderId));
      } catch (err) {
        alert("Failed to delete order.");
      }
    }
  };

  // Filter orders based on active tab and search query
  const filteredOrders = orders.filter((order) => {
    const matchesSearch =
      (order.customer_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (order.customer_phone || '').includes(searchQuery);

    const orderStatus = (order.status || 'pending').toLowerCase();
    
    // Support Completed status mapped under Delivered
    const matchesStatus =
      activeTab === 'all' ||
      (activeTab === 'delivered' && (orderStatus === 'delivered' || orderStatus === 'completed')) ||
      orderStatus === activeTab;

    return matchesSearch && matchesStatus;
  });

  const tabs: Array<{ id: typeof activeTab; name: string }> = [
    { id: 'all', name: 'All Orders' },
    { id: 'pending', name: 'Pending' },
    { id: 'approved', name: 'Approved' },
    { id: 'processing', name: 'Processing' },
    { id: 'delivered', name: 'Delivered' },
    { id: 'rejected', name: 'Rejected' },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Orders Pipeline</h1>
          <p className="mt-1 text-sm text-slate-500">
            View, search, and manage all phone sales order structures in real-time.
          </p>
        </div>
        <LinkComponent
          href="/create-order"
          className="inline-flex items-center justify-center px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-colors shadow-sm w-fit"
        >
          Add Manual Order
        </LinkComponent>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200 shadow-sm">
        {/* Tabs */}
        <div className="flex flex-wrap gap-1.5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-colors cursor-pointer border ${
                activeTab === tab.id
                  ? 'bg-white text-slate-900 border-slate-300 shadow-xs'
                  : 'text-slate-650 hover:bg-slate-200/50 hover:text-slate-900 border-transparent'
              }`}
            >
              {tab.name}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative max-w-xs w-full">
          <input
            type="text"
            placeholder="Search by customer name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-white border border-slate-300 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
          />
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Orders Table Panel */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 flex flex-col shadow-sm">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-slate-450">Loading order list...</div>
        ) : error ? (
          <div className="py-16 text-center text-sm text-red-500 font-medium">{error}</div>
        ) : filteredOrders.length === 0 ? (
          <div className="py-16 text-center text-sm text-slate-500">
            No orders match the current search filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-left">
              <thead>
                <tr className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100">
                  <th className="py-3 px-4">Order ID</th>
                  <th className="py-3 px-4">Customer Details</th>
                  <th className="py-3 px-4">Items Summary</th>
                  <th className="py-3 px-4">Delivery Coordinates</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-650">
                {filteredOrders.map((order) => (
                  <tr key={order.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-4 font-mono text-xs text-slate-450 font-bold">
                      {order.id}
                    </td>
                    <td className="py-4 px-4">
                      <div className="font-bold text-slate-900">
                        {order.customer_name || 'Anonymous Customer'}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {order.customer_phone || 'No Phone'}
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="text-xs font-bold text-slate-800">
                        {order.items.map((i) => `${i.quantity}x ${i.name}`).join(', ')}
                      </div>
                      <div className="text-[10px] text-slate-500 mt-0.5 font-medium">
                        Total Value: ₹{order.items.reduce((sum, item) => sum + (item.quantity * (item.price || 0)), 0).toFixed(2)}
                      </div>
                    </td>
                    <td className="py-4 px-4 max-w-xs">
                      <div className="truncate text-slate-700 font-semibold">{order.delivery_address}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Time: {order.delivery_time || 'Unspecified'}</div>
                    </td>
                    <td className="py-4 px-4">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
                        order.status === 'completed' || order.status === 'delivered'
                          ? 'bg-emerald-50 text-emerald-705 border-emerald-200'
                          : order.status === 'approved'
                          ? 'bg-indigo-50 text-indigo-705 border-indigo-200'
                          : order.status === 'rejected'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : 'bg-amber-50 text-amber-705 border-amber-250'
                      }`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <LinkComponent
                          href={`/action-card?id=${order.id}`}
                          className="text-[11px] font-bold text-indigo-650 hover:text-indigo-850 hover:underline"
                        >
                          View
                        </LinkComponent>
                        <span className="text-slate-200">|</span>
                        <LinkComponent
                          href={`/action-card?id=${order.id}&edit=true`}
                          className="text-[11px] font-bold text-amber-600 hover:text-amber-800 hover:underline"
                        >
                          Edit
                        </LinkComponent>
                        <span className="text-slate-200">|</span>
                        <button
                          onClick={() => handleDelete(order.id)}
                          className="text-[11px] font-bold text-red-600 hover:text-red-800 hover:underline cursor-pointer border-none bg-transparent"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
