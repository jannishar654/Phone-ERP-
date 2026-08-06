'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

type ChapterLink = { id: string; path: string; title: string };

export default function DocsNavigation({ chapters }: { chapters: ChapterLink[] }) {
  const [activeChapter, setActiveChapter] = useState(chapters[0]?.id ?? '');
  const activePageRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const openHashChapter = () => {
      const chapterId = window.location.hash.slice(1);
      if (!chapters.some((chapter) => chapter.id === chapterId)) return;

      setActiveChapter(chapterId);
      window.requestAnimationFrame(() => {
        document.getElementById(chapterId)?.scrollIntoView({ block: 'start' });
      });
    };

    openHashChapter();
    window.addEventListener('hashchange', openHashChapter);
    return () => window.removeEventListener('hashchange', openHashChapter);
  }, [chapters]);

  useEffect(() => {
    const activePage = activePageRef.current;
    const navigation = activePage?.parentElement;
    if (!activePage || !navigation) return;

    navigation.scrollTo({
      left: activePage.offsetLeft - (navigation.clientWidth - activePage.offsetWidth) / 2,
      behavior: 'smooth',
    });
  }, [activeChapter]);

  useEffect(() => {
    const targets = chapters
      .map((chapter) => document.getElementById(chapter.id))
      .filter((element): element is HTMLElement => Boolean(element));

    if (!targets.length || !('IntersectionObserver' in window)) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveChapter(visible[0].target.id);
      },
      { rootMargin: '-18% 0px -70% 0px', threshold: 0 },
    );

    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, [chapters]);

  return (
    <nav className="docs-page-navigation" aria-label="Documentation chapters">
      {chapters.map((chapter) => {
        const isActive = activeChapter === chapter.id;
        return (
          <Link
            key={chapter.id}
            ref={isActive ? activePageRef : undefined}
            href={`/docs#${chapter.id}`}
            className={isActive ? 'is-active' : ''}
          >
            {chapter.title}
          </Link>
        );
      })}
    </nav>
  );
}
