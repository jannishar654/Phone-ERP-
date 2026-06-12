import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const session = request.cookies.get('phoneerp-session')?.value;

  // Protected routes list
  const protectedRoutes = [
    '/dashboard',
    '/orders',
    '/create-order',
    '/action-card',
    '/action-cards',
    '/upload',
    '/settings'
  ];

  // Auth pages list
  const authRoutes = ['/login', '/signup'];

  const isProtectedRoute = protectedRoutes.some(route => pathname.startsWith(route));
  const isAuthRoute = authRoutes.some(route => pathname === route);

  if (isProtectedRoute && !session) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('redirectTo', pathname);
    return NextResponse.redirect(url);
  }

  if (isAuthRoute && session) {
    const url = request.nextUrl.clone();
    url.pathname = '/dashboard';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/orders/:path*',
    '/create-order/:path*',
    '/action-card/:path*',
    '/action-cards/:path*',
    '/upload/:path*',
    '/settings/:path*',
    '/login',
    '/signup'
  ],
};
