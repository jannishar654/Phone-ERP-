import type { Metadata } from 'next';
import PublicPageShell from '@/components/public/PublicPageShell';
import { publicSite } from '@/lib/public-site';

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: 'Terms governing business use of PhoneERP.',
};

export default function TermsPage() {
  return (
    <PublicPageShell
      eyebrow="Legal"
      title="Terms of Service"
      summary="These terms govern access to PhoneERP by business owners, administrators, staff and authorised pilot participants."
    >
      <p><strong>Effective date:</strong> {publicSite.effectiveDate}</p>
      <p><strong>Last updated:</strong> {publicSite.lastUpdatedDate}</p>

      <section>
        <h2>1. Operator and acceptance</h2>
        <p>{publicSite.operatorDisclosure}</p>
        <p>By creating an account, connecting a business channel or using PhoneERP, you agree to these terms and the Privacy Policy. If you act for a business, you confirm that you are authorised to bind that business.</p>
      </section>

      <section>
        <h2>2. Service description</h2>
        <p>PhoneERP helps businesses receive supported customer communications, classify requests, extract structured order details, review action cards, manage fulfilment workflows, send operational messages and provide customer tracking or invoices. Features may be experimental, changed or limited during a pilot.</p>
      </section>

      <section>
        <h2>3. Business responsibilities</h2>
        <ul>
          <li>Provide accurate registration, catalogue, pricing, staff and integration information.</li>
          <li>Review AI-generated content before relying on it for fulfilment, billing, medical, dietary or safety-sensitive decisions.</li>
          <li>Maintain authority over connected accounts, phone numbers, customer data and staff access.</li>
          <li>Obtain required customer notices, consent or other lawful basis for processing messages and personal information.</li>
          <li>Keep credentials secure and promptly report unauthorised use.</li>
        </ul>
      </section>

      <section>
        <h2>4. Communication channels and acceptable use</h2>
        <p>Businesses must comply with the policies of each enabled provider, including Meta&apos;s WhatsApp policies and Telegram&apos;s Bot Platform terms, plus applicable consent, anti-spam and consumer-protection laws. PhoneERP must not be used for spam, purchased contact lists, deceptive messages, unlawful products, harassment or unauthorised marketing. A business remains responsible for its connected accounts, bots, messages, templates and customer relationships.</p>
      </section>

      <section>
        <h2>5. Fees and provider charges</h2>
        <p>Any PhoneERP subscription, setup or support fee will be disclosed before it is charged. Unless agreed otherwise in writing, each business is responsible for Meta conversation or template charges, telecommunications costs, taxes and charges from other enabled providers. Pilot access does not guarantee permanently free service.</p>
      </section>

      <section>
        <h2>6. Availability and limitations</h2>
        <p>We aim to provide a reliable service but do not guarantee uninterrupted availability, perfect transcription, error-free AI extraction, message delivery or compatibility with every number, device, language or provider account. Third-party outages, policy changes, account reviews and messaging limits may affect the service. Businesses should maintain a reasonable manual fallback for important orders.</p>
      </section>

      <section>
        <h2>7. Suspension</h2>
        <p>We may restrict or suspend access to protect customers, another tenant, PhoneERP or a provider; investigate suspected abuse or security incidents; respond to legal requirements; address non-payment; or enforce these terms. Where practical, we will explain the issue and provide a path to resolution.</p>
      </section>

      <section>
        <h2>8. Intellectual property</h2>
        <p>PhoneERP retains rights in its software, workflows, design, documentation and platform technology. Businesses retain rights in their catalogue, brand and submitted business content. Customers and businesses retain applicable rights in their original messages and data. You grant PhoneERP a limited right to process submitted content only to provide, secure and improve the service.</p>
      </section>

      <section>
        <h2>9. Liability</h2>
        <p>To the extent permitted by law, PhoneERP is provided on an &quot;as available&quot; basis. The operator is not liable for indirect, incidental, special or consequential loss, lost profits, missed orders, incorrect AI output or third-party platform action. Nothing in these terms excludes liability that cannot legally be excluded. During an unpaid pilot, aggregate liability is limited to the amount paid to PhoneERP for the service in the three months before the claim.</p>
      </section>

      <section>
        <h2>10. Termination and disconnection</h2>
        <p>A business may stop using PhoneERP and disconnect a supported channel or request account deletion at any time. Termination does not remove accrued payment obligations or records that must be retained by law. Disconnecting PhoneERP does not delete a business-owned Meta account or Telegram bot.</p>
      </section>

      <section>
        <h2>11. Governing law and contact</h2>
        <p>These terms are governed by the laws of India. Disputes are subject to courts of competent jurisdiction in New Delhi, India, unless applicable law requires otherwise. Questions may be sent to <a href={`mailto:${publicSite.contactEmail}`}>{publicSite.contactEmail}</a>.</p>
      </section>
    </PublicPageShell>
  );
}
