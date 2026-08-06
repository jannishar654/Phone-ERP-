import type { ReactNode } from 'react';
import PublicSiteShell from './PublicSiteShell';

type EditorialPageProps = {
  eyebrow: string;
  title: string;
  summary: string;
  children: ReactNode;
};

export default function EditorialPage({ eyebrow, title, summary, children }: EditorialPageProps) {
  return (
    <PublicSiteShell>
      <header className="public-page-hero">
        <div className="public-container">
          <p className="public-kicker">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{summary}</p>
        </div>
      </header>
      {children}
    </PublicSiteShell>
  );
}
