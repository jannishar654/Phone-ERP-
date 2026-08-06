import type { ReactNode } from 'react';
import PublicSiteShell from './PublicSiteShell';

type PublicPageShellProps = { eyebrow: string; title: string; summary: string; children: ReactNode };

export default function PublicPageShell({ eyebrow, title, summary, children }: PublicPageShellProps) {
  return (
    <PublicSiteShell>
      <header className="public-page-hero"><div className="public-container"><p className="public-kicker">{eyebrow}</p><h1>{title}</h1><p>{summary}</p></div></header>
      <div className="public-container"><article className="legal-content public-legal-article">{children}</article></div>
    </PublicSiteShell>
  );
}
