'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Loader2 } from 'lucide-react';
import { exchangeCustomerLink } from '@/lib/api_customer';

function AccessExchange() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const legacyQueryToken = searchParams.get('token');
  const [error, setError] = useState('');

  useEffect(() => {
    const fragmentToken = new URLSearchParams(window.location.hash.slice(1)).get('token');
    const token = fragmentToken || legacyQueryToken;
    if (!token) {
      queueMicrotask(() => setError('This customer access link is incomplete.'));
      return;
    }
    exchangeCustomerLink(token)
      .then(() => router.replace('/customer/orders'))
      .catch((err) => setError(err instanceof Error ? err.message : 'This link is invalid or expired.'));
  }, [legacyQueryToken, router]);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-16 flex items-center justify-center">
      <section className="w-full max-w-md bg-white border border-slate-200 p-6 shadow-sm rounded-lg text-center">
        {error ? (
          <>
            <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-4" aria-hidden="true" />
            <h1 className="text-xl font-bold text-slate-900">Access link unavailable</h1>
            <p className="mt-2 text-sm text-slate-600">{error}</p>
            <p className="mt-4 text-sm text-slate-500">Send “track my order” on WhatsApp to receive a fresh link.</p>
          </>
        ) : (
          <>
            <Loader2 className="h-10 w-10 text-indigo-600 mx-auto mb-4 animate-spin" aria-hidden="true" />
            <h1 className="text-xl font-bold text-slate-900">Opening your orders</h1>
            <p className="mt-2 text-sm text-slate-600">Verifying your private access link.</p>
          </>
        )}
      </section>
    </main>
  );
}

export default function CustomerAccessPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-600">Opening customer portal...</main>}>
      <AccessExchange />
    </Suspense>
  );
}
