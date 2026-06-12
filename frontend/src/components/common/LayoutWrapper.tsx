'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { mockSupabaseAuth, User } from '@/lib/supabase/client';

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  const isAuthOrLanding = pathname === '/' || pathname === '/login' || pathname === '/signup';

  useEffect(() => {
    setUser(mockSupabaseAuth.getUser());
  }, [pathname]);

  const handleSignOut = async () => {
    await mockSupabaseAuth.signOut();
    router.push('/');
  };

  if (isAuthOrLanding) {
    return <div className="min-h-screen w-full bg-white text-slate-900">{children}</div>;
  }

  return (
    <div className="min-h-screen flex bg-white text-slate-900">
      <Sidebar />
      
      <div className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        <header className="h-16 border-b border-slate-200 flex items-center justify-between px-8 bg-white sticky top-0 z-10">
          <div className="flex items-center space-x-4">
            <span className="text-sm font-semibold text-slate-400">Workspace</span>
            <span className="text-xs text-slate-300">/</span>
            <span className="text-sm text-slate-700 font-medium">PhoneERP System</span>
          </div>
          
          <div className="flex items-center space-x-6 text-xs text-slate-500">
            {user && (
              <div className="flex items-center space-x-2">
                <span className="h-2 w-2 rounded-full bg-indigo-600"></span>
                <span className="text-slate-800 text-sm font-medium">Hello, {user.name}</span>
              </div>
            )}
            
            <button
              onClick={handleSignOut}
              className="text-slate-550 hover:text-red-600 font-semibold transition-colors cursor-pointer text-sm"
            >
              Sign Out
            </button>
          </div>
        </header>

        <main className="flex-1 p-8 bg-white">
          {children}
        </main>
      </div>
    </div>
  );
}
