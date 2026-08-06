import type { ReactNode } from 'react';
import PublicFooter from './PublicFooter';
import PublicNavigation from './PublicNavigation';
import PublicScrollEffects from './PublicScrollEffects';

export default function PublicSiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="public-site">
      <PublicNavigation />
      <PublicScrollEffects />
      <main>{children}</main>
      <PublicFooter />
    </div>
  );
}
