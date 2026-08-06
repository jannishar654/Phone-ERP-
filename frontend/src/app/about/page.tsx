import { ArrowUpRight, UserRound } from 'lucide-react';
import EditorialPage from '@/components/public/EditorialPage';

const team = [
  { name: 'Danish', role: 'Team lead and product engineering', href: 'https://www.linkedin.com/in/danish90654/' },
  { name: 'Jannishar', role: 'Engineering and workflow development', href: 'https://www.linkedin.com/in/mohammad-jannishar-b8211728b/' },
  { name: 'Nasir', role: 'Engineering and business workflow research', href: 'https://www.linkedin.com/in/codernesi/' },
];

export default function AboutPage() {
  return (
    <EditorialPage eyebrow="About" title="Built from the way small businesses actually receive orders." summary="PhoneERP is developed by the Mixorg team through direct workflow study, production testing and feedback from small businesses.">
      <section className="public-section"><div className="public-container public-feature-split public-grid-2"><div><p className="public-kicker">The problem</p><h2>Important order details are buried inside calls, chats and voice notes.</h2></div><div className="public-copy"><p>Products, quantities, addresses and delivery timings are often copied manually into separate tools. Details are missed, staff coordination is informal, and customers repeatedly ask for updates.</p><p>PhoneERP turns that conversation into structured work without forcing a small business to begin with a complex enterprise system.</p></div></div></section>
      <section className="public-section"><div className="public-container public-note-band"><p className="public-kicker">Product principle</p><h2>Automation should reduce coordination work, not remove business control.</h2><p>The team is validating the product with grocery and restaurant workflows, prioritising clear review, visible exceptions, customer context and practical operational handoffs.</p></div></section>
      <section className="public-section">
        <div className="public-container">
          <div className="public-section-heading">
            <p className="public-kicker">The team</p>
            <h2>
              Built by{' '}
              <a className="public-inline-link" href="https://www.linkedin.com/company/mixorg/" target="_blank" rel="noreferrer">
                Mixorg <ArrowUpRight aria-hidden="true" />
              </a>
            </h2>
            <p>Product thinking, engineering and on-ground business validation come together in one team.</p>
          </div>
          <div className="public-team-list">
            {team.map((member) => (
              <a key={member.name} href={member.href} target="_blank" rel="noreferrer" aria-label={`${member.name} on LinkedIn`}>
                <span className="public-team-link-icon"><UserRound aria-hidden="true" /></span>
                <span>
                  <strong>{member.name}</strong>
                  <small>{member.role}</small>
                </span>
                <ArrowUpRight aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      </section>
    </EditorialPage>
  );
}
