import Link from 'next/link';
import type { ReactNode } from 'react';
import PublicSiteShell from './PublicSiteShell';

export const docsNavigation = [
  ['', 'Overview'],
  ['getting-started', 'Getting started'],
  ['catalog', 'Catalog setup'],
  ['channels', 'Order channels'],
  ['whatsapp', 'WhatsApp'],
  ['telegram', 'Telegram'],
  ['business-configuration', 'Business configuration'],
  ['order-lifecycle', 'Order lifecycle'],
  ['customer-portal', 'Customer portal'],
  ['roles-and-permissions', 'Roles and permissions'],
  ['troubleshooting', 'Troubleshooting'],
] as const;

export default function DocsShell({ slug, title, summary, children }: { slug: string; title: string; summary: string; children: ReactNode }) {
  return (
    <PublicSiteShell>
      <div className="docs-layout public-container">
        <aside className="docs-sidebar">
          <p className="public-kicker">Documentation</p>
          <nav aria-label="Documentation navigation">
            {docsNavigation.map(([path, label]) => (
              <Link key={path} href={path ? `/docs/${path}` : '/docs'} className={slug === path ? 'is-active' : ''}>{label}</Link>
            ))}
          </nav>
        </aside>
        <article className="docs-article">
          <header><p className="public-kicker">PhoneERP docs</p><h1>{title}</h1><p>{summary}</p></header>
          <div className="docs-content">{children}</div>
        </article>
      </div>
    </PublicSiteShell>
  );
}
