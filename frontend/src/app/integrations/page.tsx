import Link from 'next/link';
import { ArrowRight, MessageCircle, Send, Webhook } from 'lucide-react';
import EditorialPage from '@/components/public/EditorialPage';

const channels = [
  {
    title: 'Meta WhatsApp Cloud API',
    description: 'An official production number can receive text and voice notes through verified webhooks. Self-service onboarding for unrelated businesses is still in progress.',
    status: 'Connected pilot',
    icon: MessageCircle,
    href: '/integrations/whatsapp',
  },
  {
    title: 'Twilio WhatsApp',
    description: 'An assisted provider path used for customer intake and delivery notifications during pilots.',
    status: 'Pilot alternative',
    icon: Webhook,
  },
  {
    title: 'Telegram',
    description: 'Text and voice-note intake routed into the same intent, extraction and action-card workflow.',
    status: 'Pilot alternative',
    icon: Send,
  },
];

export default function IntegrationsPage() {
  return (
    <EditorialPage
      eyebrow="Integrations"
      title="Channels connect once. The workflow stays consistent."
      summary="PhoneERP normalises supported providers into the same message and order pipeline. Direct Meta connectivity is in pilot, while scalable self-service onboarding remains in development."
    >
      <section className="public-section">
        <div className="public-container public-capability-list">
          {channels.map((channel) => {
            const Icon = channel.icon;
            return (
              <article key={channel.title}>
                <Icon size={19} />
                <div>
                  <span className="public-channel-status">{channel.status}</span>
                  <h2>{channel.title}</h2>
                  <p>{channel.description}</p>
                  {channel.href && (
                    <Link href={channel.href}>
                      WhatsApp integration guide <ArrowRight size={14} />
                    </Link>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>
      <section className="public-section">
        <div className="public-container public-note-band">
          <p className="public-kicker">Pilot operations</p>
          <h2>Twilio and Telegram remain practical assisted channels while Meta onboarding is completed.</h2>
          <p>They can support controlled business pilots today, but they are not a substitute for owner alerts, a shared conversation inbox or scalable connection of each business&apos;s own WhatsApp number.</p>
        </div>
      </section>
    </EditorialPage>
  );
}
