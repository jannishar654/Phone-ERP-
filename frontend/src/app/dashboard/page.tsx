'use client';

import { useState } from 'react';
import Link from 'next/link';
import { getActionCards, getOrders } from '@/lib/api';
import { ActionCard } from '@/types';
import MetricCard from '@/components/dashboard/MetricCard';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';

interface DashboardOrder {
  lifecycle_status: string | null;
}

export default function Dashboard() {
  const [cards, setCards] = useState<ActionCard[]>([]);
  const [orders, setOrders] = useState<DashboardOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { lastUpdated, refreshError, manualRefresh } = useAutoRefresh(async (isSilent) => {
    try {
      if (!isSilent && cards.length === 0 && orders.length === 0) setIsLoading(true);
      const [cardsData, ordersData] = await Promise.all([
        getActionCards(),
        getOrders().catch(() => []) // fallback safely
      ]);
      setCards(cardsData);
      setOrders(ordersData);
    } catch (err: unknown) {
      if (!isSilent && cards.length === 0 && orders.length === 0) {
        setError('Failed to fetch dashboard metrics from backend.');
      } else {
        throw err;
      }
    } finally {
      if (!isSilent) setIsLoading(false);
    }
  }, 10000);

  const pendingActionCards = cards.filter(c => c.status.toLowerCase() === 'pending').length;
  
  const packingOrders = orders.filter(o => {
    const s = o.lifecycle_status;
    return !s || s === 'pending_review' || s === 'packing';
  }).length;

  const outForDeliveryOrders = orders.filter(o => o.lifecycle_status === 'out_for_delivery').length;
  const deliveredOrders = orders.filter(o => o.lifecycle_status === 'delivered').length;

  const metrics = [
    { name: 'Pending Review (Action Cards)', value: pendingActionCards, color: 'text-amber-600' },
    { name: 'Packing Orders', value: packingOrders, color: 'text-indigo-600' },
    { name: 'Out for Delivery Orders', value: outForDeliveryOrders, color: 'text-emerald-600' },
    { name: 'Delivered Orders', value: deliveredOrders, color: 'text-cyan-600' },
  ];

  const recentCards = cards.slice(0, 5); // Take top 5 recent

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 sm:space-y-8">
      {/* Title section */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-slate-900">Dashboard Overview</h1>
          <p className="mt-1 text-sm text-slate-500">
            Monitor your customer phone transcriptions, manual order submissions, and ERP dispatch workflow.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3 self-start">
          {refreshError && <span className="text-xs text-red-500 hidden sm:inline" title={refreshError}>Unable to refresh. Showing previously loaded data.</span>}
          {lastUpdated && !refreshError && <span className="text-xs text-slate-500 hidden sm:inline">Last updated: {lastUpdated.toLocaleTimeString()}</span>}
          <button onClick={manualRefresh} className="text-xs px-3 py-1.5 bg-white border border-slate-200 text-slate-700 font-semibold rounded-lg hover:bg-slate-50 transition-colors shadow-sm">
            Refresh
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.name}
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
        <div className="lg:col-span-2 rounded-lg border border-slate-200 bg-white p-4 sm:p-6 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-slate-900">Recent Orders</h2>
            <Link
              href="/orders"
              className="text-sm font-semibold text-blue-600 hover:text-blue-800 transition-colors"
            >
              View All
            </Link>
          </div>

          {isLoading ? (
            <div className="py-12 text-center text-sm text-slate-400">Loading orders...</div>
          ) : error ? (
            <div className="py-12 text-center text-sm text-red-500 font-medium">{error}</div>
          ) : recentCards.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-500">No orders found. Create one to get started!</div>
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-full divide-y divide-slate-100 text-left">
                <thead>
                  <tr className="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-slate-100">
                    <th className="py-3 px-4">Customer</th>
                    <th className="py-3 px-4">Address</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm text-slate-600">
                  {recentCards.map((card) => (
                    <tr key={card.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-4">
                        <Link href={`/action-card?id=${card.id}`} className="font-bold text-slate-900 hover:text-indigo-600 transition-colors block">
                          {card.customer_name || 'Anonymous Customer'}
                        </Link>
                        <div className="text-xs text-slate-400">{card.customer_phone}</div>
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
                            ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                            : card.status === 'rejected'
                            ? 'bg-red-50 text-red-700 border-red-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
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
              <div className="divide-y divide-slate-100 md:hidden">
                {recentCards.map((card) => (
                  <Link
                    key={card.id}
                    href={`/action-card?id=${card.id}`}
                    className="block py-4 first:pt-0 last:pb-0"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-slate-900">{card.customer_name || 'Anonymous Customer'}</p>
                        <p className="mt-0.5 truncate text-xs text-slate-500">{card.customer_phone || 'Phone unavailable'}</p>
                      </div>
                      <span className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                        card.status === 'completed' || card.status === 'delivered'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : card.status === 'approved'
                          ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                          : card.status === 'rejected'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}>{card.status}</span>
                    </div>
                    <p className="mt-3 line-clamp-2 text-sm font-medium text-slate-700">{card.delivery_address || 'Delivery address pending'}</p>
                    <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
                      <span className="truncate">{card.delivery_time || 'Delivery time pending'}</span>
                      <span className="shrink-0 font-semibold">{card.items.reduce((acc, item) => acc + item.quantity, 0)} items</span>
                    </div>
                  </Link>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Quick actions & stats */}
        <div className="space-y-6">
          <div className="rounded-lg border border-slate-200 bg-white p-5 sm:p-6 flex flex-col justify-between shadow-sm">
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
              <Link
                href="/access"
                className="flex items-center justify-between w-full px-4 py-3 rounded-lg bg-emerald-100 hover:bg-emerald-200/80 text-emerald-800 font-semibold text-sm transition-all border border-emerald-200 mt-3"
              >
                <span>Manage Staff Access</span>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              </Link>
            </div>
          </div>

          {/* AI Info Panel */}
          <div className="rounded-lg border border-indigo-100 bg-indigo-50/45 p-5 sm:p-6 shadow-sm">
            <h4 className="text-sm font-bold uppercase tracking-wider text-indigo-800">Order Extraction Pipeline</h4>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed font-medium">
              Customer speech audio uploads transcribe automatically. In-memory data structures map coordinates, pricing lists, and delivery timeframes into Action Cards for validation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
