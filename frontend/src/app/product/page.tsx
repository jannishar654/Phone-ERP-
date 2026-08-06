import { Bot, ClipboardCheck, MessagesSquare, PackageCheck, ReceiptIndianRupee, Users } from 'lucide-react';
import EditorialPage from '@/components/public/EditorialPage';

const capabilities = [
  [MessagesSquare, 'Conversational intake', 'Receive text and voice-note orders from WhatsApp, Telegram and supported intake channels.'],
  [Bot, 'Intent-aware AI', 'Separate orders from tracking, pricing, support and unrelated messages before extraction begins.'],
  [ClipboardCheck, 'Human review', 'Present structured, editable action cards so owners approve what the system understood.'],
  [PackageCheck, 'Operational handoff', 'Move approved work to dedicated packing and delivery queues with shop-level isolation.'],
  [Users, 'Customer continuity', 'Remember customer profiles, preserve order context and provide private order tracking.'],
  [ReceiptIndianRupee, 'Billing and notification', 'Create public invoices and notify customers when their order reaches key stages.'],
] as const;

export default function ProductPage() {
  return (
    <EditorialPage
      eyebrow="Product"
      title="An operating layer for orders that begin as conversations."
      summary="PhoneERP converts informal customer messages into structured, reviewable work while keeping the business in control."
    >
      <section className="public-section"><div className="public-container public-capability-list">
        {capabilities.map(([Icon, title, text]) => (
          <article key={title}><Icon size={19} /><div><h2>{title}</h2><p>{text}</p></div></article>
        ))}
      </div></section>
      <section className="public-section"><div className="public-container public-feature-split public-grid-2">
        <div><p className="public-kicker">Control by design</p><h2>AI proposes. The business decides.</h2></div>
        <div className="public-copy"><p>PhoneERP does not silently turn every message into an order. It classifies intent, asks for missing details when needed, and gives owners an editable review step.</p><p>Operational roles only see the work relevant to their shop and role. Customers receive a private view of their own orders.</p></div>
      </div></section>
    </EditorialPage>
  );
}
