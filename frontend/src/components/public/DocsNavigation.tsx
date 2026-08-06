'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

const docsNavigation = [
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

type SectionLink = { id: string; title: string };

export default function DocsNavigation({ slug, sections }: { slug: string; sections: SectionLink[] }) {
  const [activeSection, setActiveSection] = useState(sections[0]?.id ?? '');
  const activePageRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const activePage = activePageRef.current;
    const navigation = activePage?.parentElement;
    if (!activePage || !navigation) return;

    navigation.scrollTo({
      left: activePage.offsetLeft - (navigation.clientWidth - activePage.offsetWidth) / 2,
      behavior: 'smooth',
    });
  }, [slug]);

  useEffect(() => {
    const targets = sections
      .map((section) => document.getElementById(section.id))
      .filter((element): element is HTMLElement => Boolean(element));

    if (!targets.length || !('IntersectionObserver' in window)) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { rootMargin: '-20% 0px -65% 0px', threshold: 0 },
    );

    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, [sections]);

  return (
    <>
      <nav className="docs-page-navigation" aria-label="Documentation navigation">
        {docsNavigation.map(([path, label]) => {
          const isActive = slug === path;
          return (
            <Link
              key={path}
              ref={isActive ? activePageRef : undefined}
              href={path ? `/docs/${path}` : '/docs'}
              className={isActive ? 'is-active' : ''}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {sections.length > 1 && (
        <nav className="docs-section-navigation" aria-label="On this page">
          <p>On this page</p>
          {sections.map((section) => (
            <Link
              key={section.id}
              href={`#${section.id}`}
              className={activeSection === section.id ? 'is-active' : ''}
            >
              {section.title}
            </Link>
          ))}
        </nav>
      )}
    </>
  );
}
