'use client';

import { FormEvent, useCallback, useState } from 'react';
import {
  AlertCircle,
  Bot,
  ChevronDown,
  FileText,
  LogOut,
  MessageSquareText,
  PackageCheck,
  PencilLine,
  RefreshCw,
  Repeat2,
  Send,
  XCircle,
} from 'lucide-react';
import {
  askCustomerAssistant,
  CustomerApiError,
  createCustomerOrderRequest,
  createCustomerSupportRequest,
  CustomerOrder,
  getCustomerBillUrl,
  getCustomerOrders,
  hasCustomerSession,
  logoutCustomer,
} from '@/lib/api_customer';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';

const stages = [
  { key: 'received', label: 'Received' },
  { key: 'approved', label: 'Approved' },
  { key: 'packing', label: 'Packing' },
  { key: 'out_for_delivery', label: 'Out for delivery' },
  { key: 'delivered', label: 'Delivered' },
];

const statusIndex: Record<string, number> = {
  received: 0,
  pending_review: 0,
  approved: 1,
  packing: 2,
  out_for_delivery: 3,
  delivered: 4,
};

function OrderTimeline({ status }: { status: string }) {
  const activeIndex = statusIndex[status] ?? 0;
  const cancelled = status === 'cancelled';
  return (
    <div className="mt-5" aria-label={`Order status: ${status.replaceAll('_', ' ')}`}>
      <div className="grid grid-cols-5 gap-1">
        {stages.map((stage, index) => {
          const complete = !cancelled && index <= activeIndex;
          return (
            <div key={stage.key} className="min-w-0">
              <div className={`h-1.5 w-full rounded-sm ${complete ? 'bg-indigo-600' : 'bg-slate-200'}`} />
              <p className={`mt-2 text-[10px] sm:text-xs leading-tight ${complete ? 'font-semibold text-slate-800' : 'text-slate-400'}`}>
                {stage.label}
              </p>
            </div>
          );
        })}
      </div>
      {cancelled && (
        <div className="mt-3 flex items-center gap-2 text-sm font-medium text-red-700">
          <XCircle className="h-4 w-4" aria-hidden="true" /> Cancelled
        </div>
      )}
    </div>
  );
}

export default function CustomerOrdersPage() {
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof getCustomerOrders>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [accessExpired, setAccessExpired] = useState(false);
  const [notice, setNotice] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [assistantText, setAssistantText] = useState('');
  const [assistantReply, setAssistantReply] = useState('');
  const [supportText, setSupportText] = useState('');
  const [changeOrderId, setChangeOrderId] = useState<string | null>(null);
  const [changeText, setChangeText] = useState('');

  const loadOrders = useCallback(async (isSilent: boolean) => {
    if (!isSilent) setError('');
    try {
      if (!hasCustomerSession()) throw new CustomerApiError('Your private session has expired.', 401);
      setOverview(await getCustomerOrders());
    } catch (err) {
      if (!isSilent) {
        setAccessExpired(err instanceof CustomerApiError && err.status === 401);
        setError(err instanceof Error ? err.message : 'Unable to load orders');
      }
      throw err;
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, []);

  const { lastUpdated, refreshError, manualRefresh } = useAutoRefresh(
    loadOrders,
    15_000,
  );

  const runOrderAction = async (
    order: CustomerOrder,
    type: 'repeat_order' | 'cancel_order' | 'change_order',
    message?: string,
  ) => {
    setBusy(`${order.id}:${type}`);
    setNotice('');
    setError('');
    try {
      await createCustomerOrderRequest(order.id, type, message);
      setNotice(
        type === 'repeat_order'
          ? 'Repeat order sent to the owner for review.'
          : type === 'change_order'
            ? 'Order change sent to the owner for review.'
            : 'Cancellation request sent to the owner.',
      );
      if (type === 'change_order') {
        setChangeOrderId(null);
        setChangeText('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to submit request');
    } finally {
      setBusy(null);
    }
  };

  const requestChange = async (event: FormEvent, order: CustomerOrder) => {
    event.preventDefault();
    const message = changeText.trim();
    if (!message) return;
    await runOrderAction(order, 'change_order', message);
  };

  const openBill = async (orderId: string) => {
    setBusy(`${orderId}:bill`);
    setError('');
    try {
      const url = await getCustomerBillUrl(orderId);
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to open bill');
    } finally {
      setBusy(null);
    }
  };

  const askAssistant = async (event: FormEvent) => {
    event.preventDefault();
    if (!assistantText.trim()) return;
    setBusy('assistant');
    try {
      const response = await askCustomerAssistant(assistantText.trim());
      setAssistantReply(response.reply);
      setAssistantText('');
    } catch (err) {
      setAssistantReply(err instanceof Error ? err.message : 'Assistant is unavailable');
    } finally {
      setBusy(null);
    }
  };

  const sendSupport = async (event: FormEvent) => {
    event.preventDefault();
    if (!supportText.trim()) return;
    setBusy('support');
    setError('');
    try {
      await createCustomerSupportRequest(supportText.trim());
      setSupportText('');
      setNotice('Your message was sent to the owner.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send message');
    } finally {
      setBusy(null);
    }
  };

  const signOut = async () => {
    await logoutCustomer();
    window.location.replace('/');
  };

  if (loading) return <main className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-600">Loading orders...</main>;
  if (error && !overview) return (
    <main className="min-h-screen bg-slate-50 px-4 flex items-center justify-center">
      <section className="w-full max-w-md bg-white border border-red-100 p-6 rounded-lg text-center">
        <AlertCircle className="h-10 w-10 text-red-500 mx-auto" aria-hidden="true" />
        <h1 className="mt-4 text-xl font-bold text-slate-900">
          {accessExpired ? 'Customer access expired' : 'Orders temporarily unavailable'}
        </h1>
        <p className="mt-2 text-sm text-slate-600">{error}</p>
        {accessExpired ? (
          <p className="mt-4 text-sm text-slate-500">Send “track my order” on WhatsApp to reopen your portal.</p>
        ) : (
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 inline-flex h-10 items-center justify-center gap-2 bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Retry
          </button>
        )}
      </section>
    </main>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="min-w-0">
            <p className="text-lg font-extrabold">Phone<span className="text-indigo-600">ERP</span></p>
            <p className="text-xs text-slate-500 truncate">{overview?.shop_name}</p>
          </div>
          <button onClick={signOut} className="h-10 w-10 inline-flex items-center justify-center text-slate-600 hover:text-red-600" title="Close customer session">
            <LogOut className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 sm:px-6 py-6 sm:py-8">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <p className="text-sm text-slate-500">Hello, {overview?.customer_name}</p>
            <h1 className="text-2xl font-bold mt-1">Your orders</h1>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3">
            <div className="text-right">
              {lastUpdated && (
                <p className="text-xs text-slate-500">
                  Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              )}
              {refreshError && (
                <p className="text-xs text-red-700">Unable to refresh. Showing saved results.</p>
              )}
            </div>
            <button onClick={() => { void manualRefresh(); }} className="inline-flex h-10 items-center gap-2 px-3 border border-slate-300 bg-white text-sm font-semibold hover:bg-slate-50 rounded-md">
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> Refresh
            </button>
          </div>
        </div>

        {(notice || error) && (
          <div className={`mt-4 px-4 py-3 text-sm border rounded-md ${error ? 'bg-red-50 border-red-200 text-red-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'}`}>
            {error || notice}
          </div>
        )}

        <section className="mt-6 space-y-4">
          {overview?.orders.map((order) => {
            const isOpen = expanded === order.id;
            const canCancel = !['delivered', 'cancelled'].includes(order.lifecycle_status);
            const isApprovedOrder = order.record_type === 'order';
            return (
              <article key={order.id} className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
                <div className="p-4 sm:p-5">
                  <button onClick={() => setExpanded(isOpen ? null : order.id)} className="w-full text-left flex items-start justify-between gap-4">
                    <div>
                      <p className="font-bold">Order #{order.order_number || order.id.slice(0, 8)}</p>
                      <p className="mt-1 text-sm text-slate-500">{new Date(order.created_at).toLocaleString()}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-bold">₹{order.total_amount.toFixed(2)}</span>
                      <ChevronDown className={`h-5 w-5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
                    </div>
                  </button>
                  <OrderTimeline status={order.lifecycle_status} />
                </div>

                {isOpen && (
                  <div className="border-t border-slate-100 px-4 sm:px-5 py-4 bg-slate-50/60">
                    <div className="divide-y divide-slate-200">
                      {order.items.map((item) => (
                        <div key={item.id} className="py-2.5 flex justify-between gap-4 text-sm">
                          <span className="font-medium text-slate-800">{item.display_name || item.raw_name} <span className="font-normal text-slate-500">× {item.quantity} {item.unit || ''}</span></span>
                          <span className="font-semibold">₹{item.line_total.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                    {order.delivery_address && <p className="mt-4 text-sm text-slate-600">Delivery: {order.delivery_address}</p>}
                    {!isApprovedOrder && (
                      <p className="mt-4 text-sm font-medium text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md">
                        The owner is reviewing this order. Actions and bills become available after approval.
                      </p>
                    )}
                    {isApprovedOrder && <div className="mt-4 grid grid-cols-2 sm:flex gap-2">
                      <button onClick={() => openBill(order.id)} disabled={busy === `${order.id}:bill`} className="inline-flex h-10 items-center justify-center gap-2 px-3 bg-indigo-600 text-white text-sm font-semibold rounded-md disabled:opacity-50">
                        <FileText className="h-4 w-4" aria-hidden="true" /> Bill
                      </button>
                      <button onClick={() => runOrderAction(order, 'repeat_order')} disabled={busy === `${order.id}:repeat_order`} className="inline-flex h-10 items-center justify-center gap-2 px-3 border border-slate-300 bg-white text-sm font-semibold rounded-md disabled:opacity-50">
                        <Repeat2 className="h-4 w-4" aria-hidden="true" /> Repeat
                      </button>
                      {canCancel && (
                        <button onClick={() => { setChangeOrderId(changeOrderId === order.id ? null : order.id); setChangeText(''); }} className="inline-flex h-10 items-center justify-center gap-2 px-3 border border-slate-300 bg-white text-sm font-semibold rounded-md">
                          <PencilLine className="h-4 w-4" aria-hidden="true" /> Request change
                        </button>
                      )}
                      {canCancel && (
                        <button onClick={() => runOrderAction(order, 'cancel_order')} disabled={busy === `${order.id}:cancel_order`} className="inline-flex h-10 items-center justify-center gap-2 px-3 border border-red-200 bg-white text-red-700 text-sm font-semibold rounded-md disabled:opacity-50">
                          <XCircle className="h-4 w-4" aria-hidden="true" /> Request cancellation
                        </button>
                      )}
                    </div>}
                    {isApprovedOrder && changeOrderId === order.id && (
                      <form onSubmit={(event) => requestChange(event, order)} className="mt-3 flex flex-col sm:flex-row gap-2">
                        <label htmlFor={`change-${order.id}`} className="sr-only">Describe the requested order change</label>
                        <input
                          id={`change-${order.id}`}
                          value={changeText}
                          onChange={(event) => setChangeText(event.target.value)}
                          maxLength={2000}
                          required
                          placeholder="Example: change sugar from 10 kg to 5 kg"
                          className="min-w-0 flex-1 h-10 px-3 border border-slate-300 bg-white rounded-md text-sm"
                        />
                        <button disabled={busy === `${order.id}:change_order`} className="h-10 px-4 bg-indigo-600 text-white text-sm font-semibold rounded-md disabled:opacity-50">
                          Send for approval
                        </button>
                      </form>
                    )}
                  </div>
                )}
              </article>
            );
          })}
          {!overview?.orders.length && (
            <div className="py-16 text-center border-y border-slate-200">
              <PackageCheck className="h-10 w-10 mx-auto text-slate-400" aria-hidden="true" />
              <p className="mt-3 font-semibold">No approved orders yet</p>
              <p className="mt-1 text-sm text-slate-500">Orders appear here after the owner approves them.</p>
            </div>
          )}
        </section>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <section className="border-t border-slate-200 pt-5">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-indigo-600" aria-hidden="true" />
              <h2 className="font-bold">Order assistant</h2>
            </div>
            {assistantReply && <p className="mt-3 p-3 bg-indigo-50 border border-indigo-100 text-sm text-slate-700 rounded-md whitespace-pre-wrap">{assistantReply}</p>}
            <form onSubmit={askAssistant} className="mt-3 flex gap-2">
              <label htmlFor="assistant-message" className="sr-only">Ask about your order</label>
              <input id="assistant-message" value={assistantText} onChange={(e) => setAssistantText(e.target.value)} placeholder="Where is my order?" className="min-w-0 flex-1 h-11 px-3 border border-slate-300 rounded-md text-sm" />
              <button disabled={busy === 'assistant'} className="h-11 w-11 inline-flex items-center justify-center bg-indigo-600 text-white rounded-md disabled:opacity-50" title="Send question">
                <Send className="h-4 w-4" aria-hidden="true" />
              </button>
            </form>
          </section>

          <section className="border-t border-slate-200 pt-5">
            <div className="flex items-center gap-2">
              <MessageSquareText className="h-5 w-5 text-emerald-700" aria-hidden="true" />
              <h2 className="font-bold">Report a problem</h2>
            </div>
            <form onSubmit={sendSupport} className="mt-3 flex gap-2">
              <label htmlFor="support-message" className="sr-only">Problem details</label>
              <input id="support-message" value={supportText} onChange={(e) => setSupportText(e.target.value)} placeholder="Describe the issue" className="min-w-0 flex-1 h-11 px-3 border border-slate-300 rounded-md text-sm" />
              <button disabled={busy === 'support'} className="h-11 w-11 inline-flex items-center justify-center bg-emerald-700 text-white rounded-md disabled:opacity-50" title="Send to owner">
                <Send className="h-4 w-4" aria-hidden="true" />
              </button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
