import Link from 'next/link';
import { ArrowRight, MessageCircle, Send, Webhook } from 'lucide-react';
import EditorialPage from '@/components/public/EditorialPage';

export default function IntegrationsPage() {
  return (
    <EditorialPage eyebrow="Integrations" title="Channels connect once. The workflow stays consistent." summary="PhoneERP normalizes every supported provider into the same secure message and order pipeline.">
      <section className="public-section"><div className="public-container public-capability-list">
        <article><MessageCircle size={19} /><div><h2>Meta WhatsApp Cloud API</h2><p>Official webhook-based messaging for inbound text, voice notes, status events and business replies.</p><Link href="/integrations/whatsapp">WhatsApp integration guide <ArrowRight size={14} /></Link></div></article>
        <article><Webhook size={19} /><div><h2>Twilio WhatsApp</h2><p>The prototype provider path used to validate customer intake and delivery notifications.</p></div></article>
        <article><Send size={19} /><div><h2>Telegram</h2><p>Text and voice-note intake routed into the same intent, extraction and action-card workflow.</p></div></article>
      </div></section>
    </EditorialPage>
  );
}
