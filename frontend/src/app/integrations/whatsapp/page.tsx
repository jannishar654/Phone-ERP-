import EditorialPage from '@/components/public/EditorialPage';

export default function WhatsAppIntegrationPage() {
  return (
    <EditorialPage eyebrow="WhatsApp" title="Official WhatsApp intake, routed to the correct business." summary="PhoneERP uses Meta Cloud API webhooks and a verified phone-number mapping. It does not use WhatsApp Web automation or unofficial session libraries.">
      <section className="public-section"><div className="public-container public-timeline">
        {[
          ['Connect', 'A business owner authorizes its eligible WhatsApp Business assets through an assisted or embedded onboarding flow.'],
          ['Verify', 'PhoneERP validates the WABA and phone-number ID, then stores credentials only on the backend.'],
          ['Route', 'The shared webhook verifies Meta signatures and maps the incoming phone-number ID to the correct PhoneERP shop.'],
          ['Process', 'The message is stored, deduplicated and passed to the common intent and order pipeline.'],
          ['Operate', 'Owners review action cards and staff fulfil approved orders from their role-specific workspaces.'],
        ].map(([title, text], i) => <article key={title}><span>{String(i + 1).padStart(2, '0')}</span><div><h2>{title}</h2><p>{text}</p></div></article>)}
      </div></section>
      <section className="public-section"><div className="public-container public-note-band"><p className="public-kicker">Current availability</p><h2>A production number is connected. Scalable self-service onboarding is the next integration milestone.</h2><p>Meta Business verification, Tech Provider setup, App Review, Advanced Access and Embedded Signup are required before unrelated businesses can connect themselves at scale.</p></div></section>
    </EditorialPage>
  );
}
