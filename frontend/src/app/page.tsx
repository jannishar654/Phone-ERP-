import Link from 'next/link';
import { ArrowRight, Check, MessageSquareText, ShieldCheck, Sparkles } from 'lucide-react';
import OrderFlowVisual from '@/components/public/OrderFlowVisual';
import PublicSiteShell from '@/components/public/PublicSiteShell';

const workflow = [
  ['01', 'Capture', 'Receive customer text, voice notes and order details from connected channels.'],
  ['02', 'Understand', 'Classify intent and convert natural Hindi, Hinglish or English into structured data.'],
  ['03', 'Review', 'Give the owner an editable action card before anything enters operations.'],
  ['04', 'Fulfil', 'Move approved orders through packing, delivery, tracking and billing.'],
];

export default function LandingPage() {
  return (
    <PublicSiteShell>
      <section className="phoneerp-hero">
        <div className="public-container phoneerp-hero-grid">
          <div className="phoneerp-hero-copy">
            <p className="public-kicker"><span /> AI operations for conversational commerce</p>
            <h1>PhoneERP</h1>
            <p className="phoneerp-hero-lead">Turn WhatsApp orders into organised business operations.</p>
            <p className="phoneerp-hero-summary">
              PhoneERP understands customer messages and voice notes, creates editable orders, and keeps owners, packers, delivery teams and customers aligned.
            </p>
            <div className="phoneerp-hero-actions">
              <Link href="/how-it-works" className="public-button public-button-primary">
                View the workflow <ArrowRight size={16} />
              </Link>
              <Link href="/login" className="public-button public-button-secondary">Open workspace</Link>
            </div>
            <div className="phoneerp-trust-line">
              <span><ShieldCheck size={15} /> Human-reviewed</span>
              <span><MessageSquareText size={15} /> Multichannel</span>
              <span><Sparkles size={15} /> Hindi + Hinglish aware</span>
            </div>
          </div>
          <OrderFlowVisual />
        </div>
      </section>

      <section className="public-section" id="workflow">
        <div className="public-container">
          <div className="public-section-heading">
            <p className="public-kicker">One connected workflow</p>
            <h2>From conversation to fulfilment, without losing the context.</h2>
            <p>AI handles the repetitive interpretation. People retain control over approval, exceptions and customer relationships.</p>
          </div>
          <div className="public-panel">
            {workflow.map(([number, title, description]) => (
              <div className="public-info-row" key={number}>
                <span>{number}</span>
                <div><h3>{title}</h3><p>{description}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="public-section public-capability-section">
        <div className="public-container public-grid-2 public-feature-split">
          <div>
            <p className="public-kicker">Built around real operations</p>
            <h2>Useful after the AI has understood the message.</h2>
          </div>
          <div className="public-check-list">
            {[
              'Editable action cards before approval',
              'Catalog-aware item and price matching',
              'Packing and delivery role workspaces',
              'Private customer order tracking',
              'Delivery notifications and public invoices',
              'Production grocery workflow and restaurant pilot',
            ].map((item) => <div key={item}><Check size={15} /><span>{item}</span></div>)}
          </div>
        </div>
      </section>

      <section className="public-section">
        <div className="public-container public-status-band">
          <div>
            <p className="public-kicker">Product status</p>
            <h2>A working production prototype, becoming a reusable platform.</h2>
          </div>
          <div className="public-status-columns">
            <div><span className="status-dot status-live" /> <strong>Available now</strong><p>Order capture, review, fulfilment, tracking and billing.</p></div>
            <div><span className="status-dot status-progress" /> <strong>In progress</strong><p>Self-service WhatsApp onboarding, shared inbox, owner alerts and deeper business configuration.</p></div>
          </div>
        </div>
      </section>

      <section className="public-section public-final-cta">
        <div className="public-container">
          <p className="public-kicker">Explore the system</p>
          <h2>See what PhoneERP does, how it works, and where it is going.</h2>
          <div>
            <Link href="/docs" className="public-button public-button-primary">Read documentation <ArrowRight size={16} /></Link>
            <Link href="/about" className="public-button public-button-secondary">About the project</Link>
          </div>
        </div>
      </section>
    </PublicSiteShell>
  );
}
