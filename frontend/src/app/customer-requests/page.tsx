'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, Inbox, RefreshCw, X } from 'lucide-react';
import { decideCustomerRequest, listCustomerRequests } from '@/lib/api_access';

type CustomerRequest = {
  id: string;
  request_type: 'repeat_order' | 'cancel_order' | 'change_order' | 'support';
  message?: string;
  status: string;
  created_at: string;
  customers?: { name?: string; phone?: string };
  orders?: { order_number?: number; lifecycle_status?: string; total_amount?: number };
};

const labels: Record<CustomerRequest['request_type'], string> = {
  repeat_order: 'Repeat order',
  cancel_order: 'Cancellation',
  change_order: 'Order change',
  support: 'Customer support',
};

export default function CustomerRequestsPage() {
  const [requests, setRequests] = useState<CustomerRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError('');
    try {
      setRequests(await listCustomerRequests('pending'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load requests');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const decide = async (request: CustomerRequest, status: 'approved' | 'rejected' | 'resolved') => {
    setBusy(request.id);
    setError('');
    try {
      await decideCustomerRequest(request.id, status);
      setRequests((current) => current.filter((item) => item.id !== request.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update request');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-300 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Customer Requests</h1>
          <p className="mt-1 text-sm text-slate-500">Review repeat, cancellation and support requests.</p>
        </div>
        <button onClick={load} className="inline-flex h-10 items-center gap-2 px-3 border border-slate-300 bg-white text-sm font-semibold rounded-md hover:bg-slate-50">
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Refresh
        </button>
      </div>

      {error && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void load()}
            className="font-semibold underline underline-offset-2"
          >
            Try again
          </button>
        </div>
      )}
      {loading ? (
        <div className="py-16 text-center text-slate-500">Loading customer requests...</div>
      ) : error ? null : requests.length === 0 ? (
        <div className="py-20 text-center border-b border-slate-200">
          <Inbox className="h-10 w-10 text-slate-400 mx-auto" aria-hidden="true" />
          <p className="mt-3 font-semibold text-slate-800">No pending requests</p>
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {requests.map((request) => {
            const support = request.request_type === 'support';
            return (
              <article key={request.id} className="bg-white border border-slate-200 rounded-lg p-4 sm:p-5 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-slate-900">{labels[request.request_type]}</span>
                      <span className="px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold rounded-sm">Pending</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-700">
                      {request.customers?.name || 'Customer'}
                      {request.customers?.phone ? ` · ${request.customers.phone}` : ''}
                    </p>
                    {request.orders && (
                      <p className="mt-1 text-sm text-slate-500">
                        Order #{request.orders.order_number || '—'} · {request.orders.lifecycle_status?.replaceAll('_', ' ') || 'unknown'} · ₹{Number(request.orders.total_amount || 0).toFixed(2)}
                      </p>
                    )}
                    {request.message && <p className="mt-3 text-sm text-slate-700 whitespace-pre-wrap">{request.message}</p>}
                    <p className="mt-3 text-xs text-slate-400">{new Date(request.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={() => decide(request, support ? 'resolved' : 'approved')} disabled={busy === request.id} className="inline-flex h-10 items-center gap-2 px-3 bg-emerald-700 text-white text-sm font-semibold rounded-md disabled:opacity-50">
                      <Check className="h-4 w-4" aria-hidden="true" /> {support ? 'Resolve' : 'Approve'}
                    </button>
                    <button onClick={() => decide(request, 'rejected')} disabled={busy === request.id} className="inline-flex h-10 items-center gap-2 px-3 border border-red-200 text-red-700 bg-white text-sm font-semibold rounded-md disabled:opacity-50">
                      <X className="h-4 w-4" aria-hidden="true" /> Reject
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
