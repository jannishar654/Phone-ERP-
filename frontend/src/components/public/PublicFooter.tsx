import Link from 'next/link';
import PhoneERPLogo from '@/components/brand/PhoneERPLogo';

const groups = [
  {
    title: 'Product',
    links: [
      ['/product', 'Overview'],
      ['/how-it-works', 'Workflow'],
      ['/businesses', 'Businesses'],
      ['/integrations', 'Integrations'],
    ],
  },
  {
    title: 'Resources',
    links: [
      ['/docs', 'Documentation'],
      ['/about', 'About'],
      ['/contact', 'Contact'],
      ['/support', 'Support'],
    ],
  },
  {
    title: 'Legal',
    links: [
      ['/privacy', 'Privacy'],
      ['/terms', 'Terms'],
      ['/data-deletion', 'Data deletion'],
    ],
  },
] as const;

export default function PublicFooter() {
  return (
    <footer className="public-footer">
      <div className="public-container public-footer-grid">
        <div className="public-footer-brand">
          <PhoneERPLogo />
          <p>Conversational orders, structured into real operations.</p>
          <span>Built for practical business workflows in India.</span>
        </div>
        {groups.map((group) => (
          <div key={group.title}>
            <p className="public-kicker">{group.title}</p>
            <div className="public-footer-links">
              {group.links.map(([href, label]) => (
                <Link key={href} href={href}>{label}</Link>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="public-container public-footer-bottom">
        <span>&copy; {new Date().getFullYear()} PhoneERP project team.</span>
        <span>Pilot-stage software. Human review remains part of the workflow.</span>
      </div>
    </footer>
  );
}
