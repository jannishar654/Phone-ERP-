import Link from 'next/link';
import EditorialPage from '@/components/public/EditorialPage';
import { publicSite } from '@/lib/public-site';

export default function ContactPage() {
  return (
    <EditorialPage eyebrow="Contact" title="Talk to the PhoneERP team." summary="For pilot discussions, integration questions, privacy requests or product support, contact the team by email.">
      <section className="public-section">
        <div className="public-container public-note-band">
          <p className="public-kicker">Email</p>
          <h2 className="public-contact-email">
            <Link href={`mailto:${publicSite.contactEmail}`}>{publicSite.contactEmail}</Link>
          </h2>
          <p>{publicSite.supportHours}. Expected response time: {publicSite.supportResponseTime}.</p>
        </div>
      </section>
    </EditorialPage>
  );
}
