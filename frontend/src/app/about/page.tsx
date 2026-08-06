import EditorialPage from '@/components/public/EditorialPage';

export default function AboutPage() {
  return (
    <EditorialPage eyebrow="About" title="Built from the way small businesses actually receive orders." summary="PhoneERP is a Team 2 internship project led by Danish with Janishar and Nasir, developed through direct workflow study and business feedback.">
      <section className="public-section"><div className="public-container public-feature-split public-grid-2"><div><p className="public-kicker">The problem</p><h2>Important order details are buried inside calls, chats and voice notes.</h2></div><div className="public-copy"><p>Products, quantities, addresses and delivery timings are often copied manually into separate tools. Details are missed, staff coordination is informal, and customers repeatedly ask for updates.</p><p>PhoneERP turns that conversation into structured work without forcing a small business to begin with a complex enterprise system.</p></div></div></section>
      <section className="public-section"><div className="public-container public-note-band"><p className="public-kicker">Product principle</p><h2>Automation should reduce coordination work, not remove business control.</h2><p>The team is validating the product with grocery and restaurant workflows, prioritising clear review, visible exceptions, customer context and practical operational handoffs.</p></div></section>
    </EditorialPage>
  );
}
