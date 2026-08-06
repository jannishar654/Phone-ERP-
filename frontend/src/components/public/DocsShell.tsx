import type { ReactNode } from 'react';
import DocsNavigation from './DocsNavigation';
import PublicSiteShell from './PublicSiteShell';

type ChapterLink = { id: string; path: string; title: string };

export default function DocsShell({ title, summary, chapters, children }: { title: string; summary: string; chapters: ChapterLink[]; children: ReactNode }) {
  return (
    <PublicSiteShell>
      <div className="docs-layout public-container">
        <aside className="docs-sidebar">
          <p className="public-kicker">Documentation</p>
          <DocsNavigation chapters={chapters} />
        </aside>
        <article className="docs-article">
          <header><p className="public-kicker">PhoneERP docs</p><h1>{title}</h1><p>{summary}</p></header>
          <div className="docs-content">{children}</div>
        </article>
      </div>
    </PublicSiteShell>
  );
}
