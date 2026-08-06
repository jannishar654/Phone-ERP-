import type { ReactNode } from 'react';
import PublicFooter from './PublicFooter';
import PublicNavigation from './PublicNavigation';

export default function PublicSiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="public-site">
      <PublicNavigation />
      <main>{children}</main>
      <PublicFooter />
    </div>
  );
}
