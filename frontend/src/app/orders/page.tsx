"use client";

import Link from "next/link";
import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  PackageCheck,
  RefreshCw,
  Truck,
  XCircle,
} from "lucide-react";
import { getOrders, updateOrderLifecycleStatus } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";

interface OrderItem {
  id: string;
  raw_name: string;
  display_name?: string;
  quantity: number;
  unit: string;
  line_total: number;
}

interface Order {
  id: string;
  total_amount: number;
  status: string;
  lifecycle_status: string | null;
  created_at: string;
  delivery_address?: string | null;
  delivery_time?: string | null;
  customer_name?: string | null;
  order_items: OrderItem[];
  orderNumber?: number;
}

type OrderCategory = "packing" | "out_for_delivery" | "delivered" | "cancelled";

const TABS: Array<{ id: OrderCategory; label: string }> = [
  { id: "packing", label: "Packing" },
  { id: "out_for_delivery", label: "Out for delivery" },
  { id: "delivered", label: "Delivered" },
  { id: "cancelled", label: "Cancelled" },
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function categoryFor(status: string | null): OrderCategory {
  if (!status || status === "pending_review" || status === "packing") return "packing";
  if (status === "out_for_delivery" || status === "delivered" || status === "cancelled") {
    return status;
  }
  return "packing";
}

function statusDetails(status: OrderCategory) {
  if (status === "delivered") return { label: "Delivered", icon: CheckCircle2 };
  if (status === "out_for_delivery") return { label: "Out for delivery", icon: Truck };
  if (status === "cancelled") return { label: "Cancelled", icon: XCircle };
  return { label: "Packing", icon: PackageCheck };
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<OrderCategory>("packing");
  const [updating, setUpdating] = useState<string | null>(null);

  const { lastUpdated, refreshError, manualRefresh, silentRefresh } = useAutoRefresh(
    async (isSilent) => {
      try {
        if (!isSilent && orders.length === 0) setLoading(true);
        const data = await getOrders();
        setOrders(data || []);
        setError("");
      } catch (requestError: unknown) {
        if (!isSilent && orders.length === 0) setError(errorMessage(requestError));
        else throw requestError;
      } finally {
        if (!isSilent) setLoading(false);
      }
    },
    10000,
  );

  const handleUpdateStatus = async (orderId: string, newStatus: OrderCategory) => {
    try {
      setUpdating(orderId);
      setError("");
      const updated = await updateOrderLifecycleStatus(orderId, newStatus);
      setOrders((current) =>
        current.map((order) =>
          order.id === orderId
            ? { ...order, lifecycle_status: updated.lifecycle_status }
            : order,
        ),
      );
      await silentRefresh();
    } catch (requestError: unknown) {
      setError(`Status update failed. ${errorMessage(requestError)}`);
    } finally {
      setUpdating(null);
    }
  };

  const filteredOrders = orders.filter(
    (order) => categoryFor(order.lifecycle_status) === activeTab,
  );

  return (
    <div className="w-full text-slate-950">
      <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link
            href="/dashboard"
            className="text-sm font-semibold text-slate-500 transition-colors hover:text-slate-950"
          >
            &larr; Dashboard
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-950">Orders and fulfilment</h1>
          <p className="mt-1 text-sm text-slate-600">
            Review active orders and move them through the delivery workflow.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-slate-500">
            {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Waiting for first refresh"}
          </span>
          <button
            type="button"
            onClick={manualRefresh}
            className="inline-flex h-10 items-center gap-2 border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-100"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </header>

      {(error || refreshError) && (
        <div role="alert" className="mt-5 flex items-start gap-3 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error || "Unable to refresh. Previously loaded orders are still shown."}</span>
        </div>
      )}

      <div className="mt-6 overflow-x-auto border-b border-slate-200" aria-label="Order status filters">
        <div className="flex min-w-max gap-7">
          {TABS.map((tab) => {
            const count = orders.filter(
              (order) => categoryFor(order.lifecycle_status) === tab.id,
            ).length;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex h-11 items-center gap-2 border-b-2 px-1 text-sm font-semibold transition-colors ${
                  activeTab === tab.id
                    ? "border-slate-950 text-slate-950"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {tab.label}
                <span className="min-w-6 bg-slate-200 px-1.5 py-0.5 text-center text-xs text-slate-700">
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div className="flex min-h-64 items-center justify-center text-sm text-slate-500">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading orders...
        </div>
      ) : filteredOrders.length === 0 ? (
        <div className="mt-6 flex min-h-64 flex-col items-center justify-center border border-dashed border-slate-300 bg-white px-6 text-center">
          <PackageCheck className="h-8 w-8 text-slate-400" />
          <h2 className="mt-3 font-semibold text-slate-900">No {TABS.find((tab) => tab.id === activeTab)?.label.toLowerCase()} orders</h2>
          <p className="mt-1 max-w-sm text-sm text-slate-500">
            New updates appear here automatically while this page is open.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
          {filteredOrders.map((order) => {
            const category = categoryFor(order.lifecycle_status);
            const details = statusDetails(category);
            const StatusIcon = details.icon;
            const displayId = order.orderNumber ?? order.id.slice(0, 8);
            return (
              <article key={order.id} className="border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
                  <div className="min-w-0">
                    <h2 className="break-words font-mono text-base font-bold text-slate-950">
                      Order #{displayId}
                    </h2>
                    <p className="mt-1 text-xs text-slate-500">
                      {new Date(order.created_at).toLocaleString("en-IN")}
                    </p>
                  </div>
                  <span className="inline-flex shrink-0 items-center gap-1.5 bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-800">
                    <StatusIcon className="h-3.5 w-3.5" /> {details.label}
                  </span>
                </div>

                {(order.customer_name || order.delivery_address || order.delivery_time) && (
                  <dl className="grid gap-3 border-b border-slate-200 py-4 text-sm sm:grid-cols-2">
                    {order.customer_name && <div><dt className="text-xs font-semibold uppercase text-slate-400">Customer</dt><dd className="mt-1 text-slate-800">{order.customer_name}</dd></div>}
                    {order.delivery_address && <div><dt className="text-xs font-semibold uppercase text-slate-400">Delivery</dt><dd className="mt-1 text-slate-800">{order.delivery_address}</dd></div>}
                    {order.delivery_time && <div className="sm:col-span-2"><dt className="text-xs font-semibold uppercase text-slate-400">Requested time</dt><dd className="mt-1 inline-flex items-center gap-1.5 text-slate-800"><Clock3 className="h-4 w-4 text-slate-400" />{order.delivery_time}</dd></div>}
                  </dl>
                )}

                <div className="divide-y divide-slate-100 py-2">
                  {(order.order_items || []).map((item) => (
                    <div key={item.id} className="flex items-start justify-between gap-4 py-2.5 text-sm">
                      <span className="min-w-0 text-slate-800">
                        {item.display_name || item.raw_name}
                        <span className="ml-1 text-slate-500">x {item.quantity} {item.unit}</span>
                      </span>
                      <span className="shrink-0 font-semibold text-slate-950">₹{item.line_total}</span>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between border-t border-slate-200 pt-4 text-base font-bold text-slate-950">
                  <span>Total</span>
                  <span>₹{order.total_amount}</span>
                </div>

                {(category === "packing" || category === "out_for_delivery") && (
                  <div className="mt-5 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                    <button
                      type="button"
                      onClick={() => handleUpdateStatus(order.id, category === "packing" ? "out_for_delivery" : "delivered")}
                      disabled={updating === order.id}
                      className="min-h-11 bg-slate-950 px-4 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {updating === order.id ? "Updating..." : category === "packing" ? "Mark out for delivery" : "Mark delivered"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleUpdateStatus(order.id, "cancelled")}
                      disabled={updating === order.id}
                      className="min-h-11 border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
