'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { getPublicBill } from '@/lib/api_access';

export default function PublicBillPage() {
  const params = useParams();
  const rawToken = params?.token;
  const token = Array.isArray(rawToken) ? rawToken[0] : rawToken;
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      if (!token) {
        setError('This bill link is invalid or expired.');
        setLoading(false);
        return;
      }
      
      try {
        const billData = await getPublicBill(token as string);
        setData(billData);
      } catch (err) {
        setError('This bill link is invalid or expired.\nPlease contact the shop owner.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  if (loading) return <div className="p-8 text-center text-slate-500 min-h-screen flex items-center justify-center">Loading your bill...</div>;
  if (error) return (
    <div className="p-8 text-center min-h-screen flex flex-col items-center justify-center bg-slate-50">
      <div className="bg-white p-6 rounded-xl shadow-sm border border-red-100 max-w-sm w-full">
        <svg className="w-12 h-12 text-red-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p className="text-slate-800 font-medium whitespace-pre-line">{error}</p>
      </div>
    </div>
  );

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-slate-50 print:bg-white pb-12">
      <div className="max-w-3xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        
        {/* Actions Bar - Hidden in Print */}
        <div className="flex justify-end print:hidden mb-4">
          <button 
            onClick={handlePrint}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Print / Save PDF
          </button>
        </div>

        {/* Bill Container */}
        <div className="bg-white print:border-none border border-slate-200 rounded-2xl p-6 sm:p-10 shadow-sm print:shadow-none">
          
          {/* Header */}
          <div className="flex flex-col sm:flex-row justify-between items-start border-b border-slate-100 pb-6 mb-6 gap-4">
            <div>
              <h1 className="text-2xl font-extrabold text-slate-900">{data.shop_name || 'Store Bill'}</h1>
              <p className="text-sm text-slate-500 mt-1">Receipt for your order</p>
            </div>
            <div className="text-left sm:text-right">
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide border print:border-slate-300 print:text-slate-800 print:bg-white ${
                data.lifecycle_status === 'delivered' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' :
                data.lifecycle_status === 'out_for_delivery' ? 'bg-indigo-100 text-indigo-800 border-indigo-200' :
                data.lifecycle_status === 'cancelled' ? 'bg-red-100 text-red-800 border-red-200' :
                'bg-amber-100 text-amber-800 border-amber-200'
              }`}>
                {data.lifecycle_status ? data.lifecycle_status.replace('_', ' ') : 'Pending'}
              </span>
              <div className="text-sm font-semibold text-slate-700 mt-2">Order #{data.order_number || data.order_id.slice(0, 8)}</div>
            </div>
          </div>

          {/* Customer & Delivery Details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8 text-sm">
            <div>
              <h3 className="font-semibold text-slate-800 mb-2 uppercase tracking-wider text-xs">Billed To</h3>
              <div className="text-slate-600 space-y-1">
                {data.customer_name ? (
                  <div className="font-medium text-slate-900">{data.customer_name}</div>
                ) : (
                  <div className="italic text-slate-400">Customer Name Unavailable</div>
                )}
                {data.customer_phone && <div>{data.customer_phone}</div>}
              </div>
            </div>
            
            <div className="sm:text-right">
              <h3 className="font-semibold text-slate-800 mb-2 uppercase tracking-wider text-xs">Delivery Details</h3>
              <div className="text-slate-600 space-y-1">
                {data.delivery_address && <div>{data.delivery_address}</div>}
                {data.delivery_time && <div><span className="font-medium text-slate-700">Time:</span> {new Date(data.delivery_time).toLocaleString()}</div>}
                {data.delivered_at && <div><span className="font-medium text-emerald-700">Delivered:</span> {new Date(data.delivered_at).toLocaleString()}</div>}
              </div>
            </div>
          </div>

          {/* Order Items */}
          <div className="mb-8">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 text-left">
                <thead>
                  <tr className="text-xs font-bold uppercase tracking-wider text-slate-500 bg-slate-50 print:bg-transparent">
                    <th className="py-3 px-3 rounded-l-lg print:rounded-none">Item</th>
                    <th className="py-3 px-3 text-right">Qty</th>
                    <th className="py-3 px-3 text-right hidden sm:table-cell">Price</th>
                    <th className="py-3 px-3 text-right rounded-r-lg print:rounded-none">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                  {data.items?.map((item: any) => (
                    <tr key={item.id} className="print:border-b print:border-slate-100">
                      <td className="py-3 px-3">
                        <div className="font-medium text-slate-900">{item.display_name || item.raw_name}</div>
                        <div className="sm:hidden text-xs text-slate-500 mt-1">@ ₹{item.unit_price?.toFixed(2) || '0.00'} / {item.unit || 'unit'}</div>
                      </td>
                      <td className="py-3 px-3 text-right whitespace-nowrap">{item.quantity} {item.unit || ''}</td>
                      <td className="py-3 px-3 text-right hidden sm:table-cell whitespace-nowrap">₹{item.unit_price?.toFixed(2) || '0.00'}</td>
                      <td className="py-3 px-3 text-right font-semibold text-slate-900 whitespace-nowrap">₹{item.line_total?.toFixed(2) || '0.00'}</td>
                    </tr>
                  ))}
                  {(!data.items || data.items.length === 0) && (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-slate-500 italic">No items found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Footer Totals */}
          <div className="border-t border-slate-100 pt-6 flex flex-col sm:flex-row justify-between gap-6 items-end">
            <div className="w-full sm:w-auto">
              <h3 className="font-semibold text-slate-800 mb-2 uppercase tracking-wider text-xs">Payment Method</h3>
              <div className="text-slate-600 text-sm capitalize bg-slate-50 print:bg-white print:border print:border-slate-200 inline-block px-3 py-1 rounded-md">
                {data.payment_method ? data.payment_method.replace('_', ' ') : 'N/A'}
              </div>
            </div>
            <div className="bg-slate-50 print:bg-transparent print:border-none p-4 rounded-xl border border-slate-100 w-full sm:w-64 flex flex-col justify-center items-end">
              <div className="text-sm text-slate-500 mb-1 font-semibold uppercase tracking-wide">Grand Total</div>
              <div className="text-3xl font-extrabold text-indigo-600 print:text-slate-900">₹{data.total_amount?.toFixed(2) || '0.00'}</div>
            </div>
          </div>

        </div>

        {/* Branding Footer */}
        <div className="text-center space-y-2 mt-8 print:mt-12">
          <p className="text-sm font-medium text-slate-600">
            Thank you for shopping with {data.shop_name || 'us'}!
          </p>
          <p className="text-xs text-slate-400 print:text-slate-500">
            Generated by PhoneERP
          </p>
        </div>

      </div>
    </div>
  );
}
