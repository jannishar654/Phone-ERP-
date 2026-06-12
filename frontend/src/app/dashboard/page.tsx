'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getActionCards } from '@/lib/api';
import { ActionCard } from '@/types';
import MetricCard from '@/components/dashboard/MetricCard';

export default function Dashboard() {
  const [cards, setCards] = useState<ActionCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const data = await getActionCards();
        setCards(data);
      } catch (err: any) {
        setError('Failed to fetch dashboard metrics from backend.');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }

    loadDashboardData();
  }, []);

  // Compute metric values dynamically based on live mock backend store
  const totalOrders = cards.length;
  const pendingOrders = cards.filter(c => c.status.toLowerCase() === 'pending').length;
  const approvedOrders = cards.filter(c => c.status.toLowerCase() === 'approved').length;
  const deliveredOrders = cards.filter(c => c.status.toLowerCase() === 'delivered' || c.status.toLowerCase() === 'completed').length;

  const metrics = [
    { name: 'Total Orders', value: totalOrders, color: 'text-indigo-650' },
    { name: 'Pending Orders', value: pendingOrders, color: 'text-amber-600' },
    { name: 'Approved Orders', value: approvedOrders, color: 'text-emerald-600' },
    { name: 'Delivered Orders', value: deliveredOrders, color: 'text-cyan-600' },
  ];

  const recentCards = cards.slice(0, 5); // Take top 5 recent

  return (
    <div className="space-y-8">
      {/* Title section */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Dashboard Overview</h1>
        <p className="mt-1 text-sm text-slate-500">
          Monitor your customer phone transcriptions, manual order submissions, and ERP dispatch workflow.
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric, idx) => (
          <MetricCard
            key={idx}
            name={metric.name}
            value={metric.value}
            color={metric.color}
            isLoading={isLoading}
          />
        ))}
      </div>

      {/* Main Grid: Recent activities & Action panels */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Recent Cards Table */}
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-6 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Recent Orders</h2>
              <p className="text-xs text-slate-500">The latest manual or voice-extracted orders in the system.</p>
            </div>
            <Link
              href="/orders"
              className="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
            >
              View All Orders &rarr;
            </Link>
          </div>

          {isLoading ? (
            <div className="py-12 text-center text-sm text-slate-400">Loading orders...</div>
          ) : error ? (
            <div className="py-12 text-center text-sm text-red-500 font-medium">{error}</div>
          ) : recentCards.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-550">No orders found. Create one to get started!</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 text-left">
                <thead>
                  <tr className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100">
                    <th className="py-3 px-4">Customer</th>
                    <th className="py-3 px-4">Address</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm text-slate-650">
                  {recentCards.map((card) => (
                    <tr key={card.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-4">
                        <Link href={`/action-card?id=${card.id}`} className="font-bold text-slate-900 hover:text-indigo-600 transition-colors block">
                          {card.customer_name || 'Anonymous Customer'}
                        </Link>
                        <div className="text-xs text-slate-450">{card.customer_phone}</div>
                      </td>
                      <td className="py-4 px-4 max-w-xs truncate">
                        <div className="truncate text-slate-700 font-medium">{card.delivery_address}</div>
                        <div className="text-xs text-slate-500 mt-0.5">Time: {card.delivery_time}</div>
                      </td>
                      <td className="py-4 px-4">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
                          card.status === 'completed' || card.status === 'delivered'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : card.status === 'approved'
                            ? 'bg-indigo-50 text-indigo-705 border-indigo-200'
                            : card.status === 'rejected'
                            ? 'bg-red-50 text-red-700 border-red-200'
                            : 'bg-amber-50 text-amber-700 border-amber-250'
                        }`}>
                          {card.status}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-right text-xs font-mono text-slate-500 font-bold">
                        {card.items.reduce((acc, item) => acc + item.quantity, 0)} items
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Quick actions & stats */}
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 flex flex-col justify-between shadow-sm">
            <div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Quick Actions</h3>
              <p className="text-sm text-slate-600 mb-6 leading-relaxed">
                Add an order manually or review raw speech transcriptions inside Action Cards.
              </p>
            </div>
            <div className="space-y-3">
              <Link
                href="/create-order"
                className="flex items-center justify-between w-full px-4 py-3 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm transition-all shadow-sm"
              >
                <span>Manual Create Order</span>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
              </Link>
              <Link
                href="/action-card"
                className="flex items-center justify-between w-full px-4 py-3 rounded-lg bg-slate-100 hover:bg-slate-200/80 text-slate-700 font-semibold text-sm transition-all border border-slate-200"
              >
                <span>Review Action Cards</span>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </Link>
            </div>
          </div>

          {/* AI Info Panel */}
          <div className="rounded-xl border border-slate-200 bg-indigo-50/45 p-6 shadow-sm">
            <h4 className="text-sm font-bold uppercase tracking-wider text-indigo-850">Order Extraction Pipeline</h4>
            <p className="mt-2 text-sm text-slate-650 leading-relaxed font-medium">
              Customer speech audio uploads transcribe automatically. In-memory data structures map coordinates, pricing lists, and delivery timeframes into Action Cards for validation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
