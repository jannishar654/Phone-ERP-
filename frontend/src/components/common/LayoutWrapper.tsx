'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { mockSupabaseAuth, User } from '@/lib/supabase/client';

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

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
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      
      <div className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        <header className="h-16 border-b border-slate-200 flex items-center justify-between px-4 sm:px-8 bg-white sticky top-0 z-10">
          <div className="flex items-center space-x-3 sm:space-x-4">
            {/* Hamburger button on mobile */}
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="lg:hidden p-2 -ml-2 rounded-lg text-slate-600 hover:bg-slate-100 focus:outline-none cursor-pointer"
              aria-label="Open sidebar"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <span className="hidden sm:inline text-sm font-semibold text-slate-400">Workspace</span>
            <span className="hidden sm:inline text-xs text-slate-300">/</span>
            <span className="text-sm text-slate-700 font-semibold lg:font-medium">PhoneERP System</span>
          </div>
          
          <div className="flex items-center space-x-4 sm:space-x-6 text-xs text-slate-500">
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

        <main className="flex-1 p-4 sm:p-8 bg-white">
          {children}
        </main>
      </div>
    </div>
  );
}
