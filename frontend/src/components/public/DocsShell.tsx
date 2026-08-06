import type { ReactNode } from 'react';
import DocsNavigation from './DocsNavigation';
import PublicSiteShell from './PublicSiteShell';

type SectionLink = { id: string; title: string };

export default function DocsShell({ slug, title, summary, sections, children }: { slug: string; title: string; summary: string; sections: SectionLink[]; children: ReactNode }) {
  return (
    <PublicSiteShell>
      <div className="docs-layout public-container">
        <aside className="docs-sidebar">
          <p className="public-kicker">Documentation</p>
          <DocsNavigation slug={slug} sections={sections} />
        </aside>
        <article className="docs-article">
          <header><p className="public-kicker">PhoneERP docs</p><h1>{title}</h1><p>{summary}</p></header>
          <div className="docs-content">{children}</div>
        </article>
      </div>
    </PublicSiteShell>
  );
}
