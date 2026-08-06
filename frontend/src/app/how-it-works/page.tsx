import EditorialPage from '@/components/public/EditorialPage';

const steps = [
  ['Customer conversation', 'A customer sends an order through text or a voice note in Hindi, Hinglish or English.'],
  ['Channel normalization', 'PhoneERP converts provider-specific payloads into one internal message format and rejects duplicates.'],
  ['Intent and extraction', 'The system identifies the request, transcribes audio when needed and extracts business-specific fields.'],
  ['Owner review', 'An action card shows items, quantities, delivery details, totals and the original customer context.'],
  ['Operational workflow', 'Approved orders appear for packing, move to delivery, and remain visible to the owner.'],
  ['Customer update', 'The customer can track progress and receives an invoice link after delivery.'],
];

export default function WorkflowPage() {
  return (
    <EditorialPage eyebrow="Workflow" title="A clear path from message to completed order." summary="One shared pipeline handles conversational intake while each role receives a focused operational view.">
      <section className="public-section"><div className="public-container public-timeline">
        {steps.map(([title, description], index) => <article key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><h2>{title}</h2><p>{description}</p></div></article>)}
      </div></section>
      <section className="public-section"><div className="public-container public-note-band"><p className="public-kicker">Failure handling</p><h2>The order update succeeds even when a customer notification provider is temporarily unavailable.</h2><p>Notification outcomes are captured separately, keeping the operational record reliable while making delivery failures visible for retry or support.</p></div></section>
    </EditorialPage>
  );
}
