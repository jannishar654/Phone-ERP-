import Link from 'next/link';
import type { ReactNode } from 'react';

const legalLinks = [
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
  { href: '/data-deletion', label: 'Data deletion' },
  { href: '/support', label: 'Support' },
];

type PublicPageShellProps = {
  eyebrow: string;
  title: string;
  summary: string;
  children: ReactNode;
};

export default function PublicPageShell({ eyebrow, title, summary, children }: PublicPageShellProps) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex min-h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="text-xl font-extrabold" aria-label="PhoneERP home">
            Phone<span className="text-indigo-600">ERP</span>
          </Link>
          <nav className="flex flex-wrap justify-end gap-x-4 gap-y-2 text-sm font-semibold text-slate-600" aria-label="Legal and support">
            {legalLinks.map((link) => (
              <Link key={link.href} href={link.href} className="hover:text-indigo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <div className="border-b border-slate-300 pb-8">
          <p className="text-sm font-bold uppercase text-indigo-700">{eyebrow}</p>
          <h1 className="mt-3 text-3xl font-extrabold leading-tight sm:text-4xl">{title}</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600 sm:text-lg">{summary}</p>
        </div>

        <article className="legal-content py-8 sm:py-10">{children}</article>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-6 text-sm text-slate-600 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <p>&copy; {new Date().getFullYear()} PhoneERP project team.</p>
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            {legalLinks.map((link) => (
              <Link key={link.href} href={link.href} className="hover:text-indigo-700">{link.label}</Link>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
