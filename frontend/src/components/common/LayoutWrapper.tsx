'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { authClient, User } from '@/lib/supabase/client';
import OwnerNotificationCenter from '@/components/OwnerNotificationCenter';

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [role, setRole] = useState<string | null>(null);
  const [isCheckingRole, setIsCheckingRole] = useState(true);

  const publicRoutes = ['/privacy', '/terms', '/data-deletion', '/support', '/docs'];
  const isPublicRoute = pathname === '/' || pathname === '/login' || pathname === '/signup' || publicRoutes.includes(pathname) || pathname.startsWith('/bill/') || pathname.startsWith('/customer/');

  useEffect(() => {
    authClient.getUser().then(setUser);
    
    if (!isPublicRoute) {
      queueMicrotask(() => setIsCheckingRole(true));
      import('@/lib/api_access').then(({ getMe }) => {
        getMe().then(me => {
          setRole(me.role);
          if (me.role === 'packer' && !pathname.startsWith('/staff/packing')) {
            router.replace('/staff/packing');
          } else if (me.role === 'delivery' && !pathname.startsWith('/staff/delivery')) {
            router.replace('/staff/delivery');
          } else if (me.role === 'owner' && pathname.startsWith('/staff/')) {
             router.replace('/dashboard');
          } else {
            setIsCheckingRole(false);
          }
        }).catch(() => {
          router.replace('/login');
        });
      });
    }
  }, [pathname, isPublicRoute, router]);

  const handleSignOut = async () => {
    await authClient.signOut();
    router.push('/');
  };

  if (isPublicRoute) {
    return <div className="min-h-screen w-full bg-white text-slate-900">{children}</div>;
  }

  if (isCheckingRole) {
    return <div className="min-h-screen flex items-center justify-center bg-white text-slate-900">Loading workspace...</div>;
  }

  const isStaff = role === 'packer' || role === 'delivery';

  if (isStaff) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
        <header className="h-16 border-b border-slate-200 flex items-center justify-between px-4 sm:px-8 bg-white sticky top-0 z-10 shadow-sm">
          <div className="flex items-center space-x-4">
             <span className="text-xl font-extrabold tracking-tight">Phone<span className="text-indigo-600">ERP</span></span>
             <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-md uppercase border border-indigo-100 shadow-sm">
               {role}
             </span>
          </div>
          <button 
             onClick={handleSignOut} 
             className="text-slate-600 hover:text-red-600 font-semibold transition-colors cursor-pointer text-sm bg-slate-100 hover:bg-red-50 px-4 py-2 rounded-lg"
          >
             Sign Out
          </button>
        </header>
        <main className="flex-1 p-4 sm:p-8">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-white text-slate-900">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      
      <div className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        <header className="h-16 border-b border-slate-200 flex items-center justify-between px-4 sm:px-8 bg-white sticky top-0 z-10">
          <div className="flex items-center space-x-3 sm:space-x-4">
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
            <span className="text-sm text-slate-700 font-semibold lg:font-medium hidden sm:inline">PhoneERP System</span>
            <span className="text-sm text-slate-700 font-semibold lg:font-medium inline sm:hidden">PhoneERP</span>
          </div>
          
          <div className="flex items-center space-x-4 sm:space-x-6 text-xs text-slate-500">
            {role === 'owner' && <OwnerNotificationCenter />}
            {user && (
              <div className="flex items-center space-x-2">
                <span className="h-2 w-2 rounded-full bg-indigo-600"></span>
                <span className="text-slate-800 text-sm font-medium">Hello, {user.name}</span>
              </div>
            )}
            
            <button
              onClick={handleSignOut}
              className="text-slate-600 hover:text-red-600 font-semibold transition-colors cursor-pointer text-sm hidden lg:block"
            >
              Sign Out
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-8 bg-slate-50">
          {children}
        </main>
      </div>
    </div>
  );
}
