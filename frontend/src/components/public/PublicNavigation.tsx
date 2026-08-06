'use client';

import Link from 'next/link';
import { Menu, X } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import PhoneERPLogo from '@/components/brand/PhoneERPLogo';
import { authClient } from '@/lib/supabase/client';

const navigation = [
  { href: '/product', label: 'Product' },
  { href: '/how-it-works', label: 'Workflow' },
  { href: '/businesses', label: 'Businesses' },
  { href: '/integrations', label: 'Integrations' },
  { href: '/docs', label: 'Docs' },
  { href: '/about', label: 'About' },
];

export default function PublicNavigation() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [hasSession, setHasSession] = useState(false);

  useEffect(() => {
    let active = true;
    authClient.getUser().then((user) => {
      if (active) setHasSession(Boolean(user));
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <header className="public-nav">
      <div className="public-container public-nav-inner">
        <PhoneERPLogo />

        <nav className="public-nav-links" aria-label="Primary navigation">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname === item.href || pathname.startsWith(`${item.href}/`) ? 'is-active' : ''}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="public-nav-actions">
          <Link href={hasSession ? '/dashboard' : '/login'} className="public-login-link">
            {hasSession ? 'Open workspace' : 'Log in'}
          </Link>
          <Link href="/how-it-works" className="public-button public-button-primary public-button-small">
            Explore PhoneERP
          </Link>
          <button
            type="button"
            className="public-menu-button"
            onClick={() => setIsOpen((value) => !value)}
            aria-expanded={isOpen}
            aria-controls="public-mobile-navigation"
            aria-label={isOpen ? 'Close navigation' : 'Open navigation'}
          >
            {isOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {isOpen && (
        <nav id="public-mobile-navigation" className="public-mobile-nav" aria-label="Mobile navigation">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href} onClick={() => setIsOpen(false)}>{item.label}</Link>
          ))}
          <Link href={hasSession ? '/dashboard' : '/login'} onClick={() => setIsOpen(false)}>
            {hasSession ? 'Open workspace' : 'Log in'}
          </Link>
        </nav>
      )}
    </header>
  );
}
