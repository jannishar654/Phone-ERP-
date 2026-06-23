"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

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
  created_at: string;
  order_items: OrderItem[];
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    if (!supabase) {
      setError("Supabase client not initialized.");
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const { data: userData } = await supabase.auth.getUser();
      if (!userData?.user) throw new Error("Not authenticated");

      const { data: shopData } = await supabase.from("shops").select("id").eq("owner_id", userData.user.id).single();
      if (!shopData) throw new Error("Shop not found. Please create a shop to view final orders.");

      const { data, error } = await supabase.from("orders").select("*, order_items(*)").eq("shop_id", shopData.id).order("created_at", { ascending: false });
      if (error) throw error;
      setOrders(data || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading orders...</div>;

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

        <div className="space-y-4">
          {orders.length === 0 ? (
            <p className="text-gray-500 text-center mt-10">No final orders yet.</p>
          ) : (
            orders.map(order => (
              <div key={order.id} className="bg-white p-4 rounded-xl shadow-sm border">
                <div className="flex justify-between items-start mb-3 border-b pb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">Order #{order.id.slice(0, 8)}</h3>
                    <p className="text-xs text-gray-500">{new Date(order.created_at).toLocaleString()}</p>
                  </div>
                  <div className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1
                    ${order.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 
                      order.status.includes('Pending Price') ? 'bg-red-100 text-red-700' :
                      'bg-green-100 text-green-700'}`}>
                    {order.status === 'pending' ? '⏳' : '✅'}
                    {order.status}
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

                <div className="flex justify-between items-center border-t pt-3 font-semibold">
                  <span>Total</span>
                  <span>₹{order.total_amount}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
