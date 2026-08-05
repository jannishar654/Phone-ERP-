'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authClient } from '@/lib/supabase/client';
import type { BusinessType } from '@/lib/api_access';

type PendingRegistration = {
  role: 'owner' | 'staff';
  businessType?: BusinessType;
  businessName?: string;
  inviteCode?: string;
};

function SignupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inviteFromUrl = searchParams.get('invite');
  
  const [role, setRole] = useState<'owner' | 'staff'>(inviteFromUrl ? 'staff' : 'owner');
  const [inviteCode, setInviteCode] = useState(inviteFromUrl || '');
  
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [businessType, setBusinessType] = useState<BusinessType>('grocery');
  const [businessName, setBusinessName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [confirmationSent, setConfirmationSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    
    if (role === 'staff' && !inviteCode.trim()) {
      setError('Invite code is required for staff registration.');
      return;
    }
    if (role === 'owner' && !businessName.trim()) {
      setError('Business name is required.');
      return;
    }

    setIsLoading(true);

    try {
      const { user, error: authError, hasSession } = await authClient.signUp(
        email,
        password,
        name,
        role,
        role === 'owner' ? businessType : undefined,
        role === 'owner' ? businessName.trim() : undefined,
      );
      if (authError) {
        setError(authError);
      } else if (user) {
        const pending: PendingRegistration = role === 'owner'
          ? { role, businessType, businessName: businessName.trim() }
          : { role, inviteCode };

        if (!hasSession) {
          window.localStorage.setItem(
            'phoneerp-pending-registration',
            JSON.stringify(pending),
          );
          setConfirmationSent(true);
          return;
        }

        if (role === 'staff') {
          try {
            const { registerStaff } = await import('@/lib/api_access');
            const res = await registerStaff(inviteCode);
            let redirectTo = '/dashboard';
            if (res.role === 'packer') {
              redirectTo = '/staff/packing';
            } else if (res.role === 'delivery') {
              redirectTo = '/staff/delivery';
            }
            router.replace(redirectTo);
            router.refresh();
          } catch (staffErr: unknown) {
            setError(staffErr instanceof Error ? staffErr.message : 'Failed to link staff account. Your account was created, but you need a valid invite.');
          }
        } else {
          try {
            const { registerOwner } = await import('@/lib/api_access');
            await registerOwner(businessType, businessName.trim());
            router.replace('/dashboard');
            router.refresh();
          } catch (ownerErr: unknown) {
            console.error('Failed to register owner', ownerErr);
            window.localStorage.setItem(
              'phoneerp-pending-registration',
              JSON.stringify(pending),
            );
            setError(ownerErr instanceof Error ? ownerErr.message : 'Account created, but business setup failed. Please sign in to retry.');
          }
        }
      }
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full p-8 rounded-2xl border border-slate-200 bg-white shadow-lg flex flex-col">
        <div className="text-center mb-8">
          <Link href="/" className="inline-block text-3xl font-extrabold text-slate-900 mb-2">
            Phone<span className="text-indigo-600">ERP</span>
          </Link>
          <h2 className="text-xl font-bold text-slate-900">Create your account</h2>
          <p className="text-xs text-slate-500 mt-1">Join as an owner or staff member</p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-red-650 text-sm font-medium">
            {error}
          </div>
        )}
        
        <div className="flex gap-2 mb-6">
          <button 
            type="button" 
            onClick={() => setRole('owner')}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg border ${role === 'owner' ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}
          >
            Owner
          </button>
          <button 
            type="button" 
            onClick={() => setRole('staff')}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg border ${role === 'staff' ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}
          >
            Staff Member
          </button>
        </div>

        {confirmationSent ? (
          <div className="space-y-5 text-center" role="status">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
              Check your email to confirm your account. Then sign in here to finish business setup.
            </div>
            <Link href="/login" className="inline-flex w-full justify-center rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700">
              Continue to sign in
            </Link>
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {role === 'staff' && (
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Invite Code
              </label>
              <input
                type="text"
                required
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                className="w-full bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
                placeholder="Paste your invite code here"
              />
            </div>
          )}

          {role === 'owner' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                  Business Name
                </label>
                <input
                  type="text"
                  required
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  maxLength={120}
                  className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
                  placeholder="Your business name"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                  Business Type
                </label>
                <select
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value as BusinessType)}
                  className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 transition-colors"
                >
                  <option value="grocery">Grocery Store</option>
                  <option value="wholesale">Wholesale Business</option>
                  <option value="restaurant">Restaurant</option>
                  <option value="pharmacy">Pharmacy</option>
                  <option value="bakery">Bakery</option>
                  <option value="hardware">Hardware Store</option>
                  <option value="general">General Business</option>
                </select>
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="John Doe"
            />
          </div>

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
              placeholder="john@company.com"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="••••••••"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Confirm Password
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-indigo-600 hover:bg-indigo-705 disabled:bg-indigo-400 text-white rounded-lg py-3 text-sm font-semibold transition-colors shadow-sm cursor-pointer"
          >
            {isLoading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>
        )}

        <div className="mt-6 text-center text-xs text-slate-500 font-medium">
          Already have an account?{' '}
          <Link href="/login" className="text-indigo-600 hover:text-indigo-850 font-bold">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center p-4">Loading...</div>}>
      <SignupContent />
    </Suspense>
  );
}
