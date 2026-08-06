'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authClient } from '@/lib/supabase/client';
import type { BusinessType } from '@/lib/api_access';
import PhoneERPLogo from '@/components/brand/PhoneERPLogo';

type PendingRegistration = {
  role: 'owner' | 'staff';
  businessType?: BusinessType;
  businessName?: string;
  inviteCode?: string;
};

function readPendingRegistration(): PendingRegistration | null {
  try {
    const raw = window.localStorage.getItem('phoneerp-pending-registration');
    return raw ? JSON.parse(raw) as PendingRegistration : null;
  } catch {
    return null;
  }
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const { user, error: authError } = await authClient.signIn(email, password);
      if (authError) {
        setError(authError);
      } else if (user) {
        try {
          const { getMe, registerOwner, registerStaff } = await import('@/lib/api_access');
          const me = await getMe();
          const pending = readPendingRegistration();
          let redirectTo = '/dashboard';
          if (me.role === 'packer') {
            redirectTo = '/staff/packing';
          } else if (me.role === 'delivery') {
            redirectTo = '/staff/delivery';
          } else if (me.role === 'none') {
            if (pending?.role === 'staff' && pending.inviteCode) {
              const registered = await registerStaff(pending.inviteCode);
              redirectTo = registered.role === 'delivery'
                ? '/staff/delivery'
                : '/staff/packing';
            } else if (pending?.role === 'owner' || user.registrationRole === 'owner') {
              await registerOwner(
                pending?.businessType || (user.businessType as BusinessType) || 'grocery',
                pending?.businessName || user.businessName || 'Default Shop',
              );
              redirectTo = '/dashboard';
            } else {
              throw new Error(
                user.registrationRole === 'staff'
                  ? 'Staff setup is incomplete. Please sign up again using a valid invite code.'
                  : 'Account setup is incomplete. Please return to sign up and choose Owner or Staff.',
              );
            }
            window.localStorage.removeItem('phoneerp-pending-registration');
          }
          
          const paramRedirect = searchParams.get('redirectTo');
          if (paramRedirect?.startsWith('/') && !paramRedirect.startsWith('//')) {
            redirectTo = paramRedirect;
          }
          
          router.replace(redirectTo);
          router.refresh();
        } catch (meErr) {
          console.error("Failed to fetch role", meErr);
          setError(meErr instanceof Error ? meErr.message : 'Unable to complete sign in. Please try again.');
        }
      }
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-theme min-h-screen flex items-center justify-center p-4">
      <div className="max-w-md w-full p-8 rounded-2xl border border-slate-200 bg-white shadow-lg flex flex-col">
        <div className="text-center mb-8">
          <PhoneERPLogo className="mb-3" />
          <h2 className="text-xl font-bold text-slate-900">Sign in to your account</h2>
          <p className="text-xs text-slate-500 mt-1">Grocery workspace, restaurant pilot and staff access</p>
        </div>

        {error && (
          <div role="alert" aria-live="polite" className="auth-error mb-6 p-4 rounded-lg border text-sm font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="alex@company.com"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Password
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-lg py-3 text-sm font-semibold transition-colors shadow-sm cursor-pointer"
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-500 font-medium">
          Don&apos;t have an account?{' '}
          <Link href="/signup" className="text-indigo-600 hover:text-indigo-800 font-bold">
            Create an account
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="auth-theme min-h-screen flex items-center justify-center p-4 font-semibold">Loading login...</div>}>
      <LoginContent />
    </Suspense>
  );
}
