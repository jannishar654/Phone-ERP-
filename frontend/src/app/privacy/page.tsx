import type { Metadata } from 'next';
import PublicPageShell from '@/components/public/PublicPageShell';
import { publicSite } from '@/lib/public-site';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'How PhoneERP collects, uses, protects, retains and deletes personal and business data.',
};

export default function PrivacyPage() {
  return (
    <PublicPageShell
      eyebrow="Legal"
      title="Privacy Policy"
      summary="This policy explains how PhoneERP handles information when businesses connect communication channels, process customer requests and manage orders."
    >
      <p><strong>Effective date:</strong> {publicSite.effectiveDate}</p>
      <p><strong>Last updated:</strong> {publicSite.lastUpdatedDate}</p>

      <section>
        <h2>1. Who operates PhoneERP</h2>
        <p>{publicSite.operatorDisclosure}</p>
        <p>For privacy questions or requests, email <a href={`mailto:${publicSite.contactEmail}`}>{publicSite.contactEmail}</a>.</p>
      </section>

      <section>
        <h2>2. Information we process</h2>
        <ul>
          <li><strong>Business account information:</strong> owner name, email, shop profile, team roles and configuration used to create and secure a PhoneERP workspace.</li>
          <li><strong>WhatsApp connection information:</strong> connected number, Meta Business or WhatsApp Business Account identifiers, Phone Number ID, connection health, permissions and encrypted credential references used to operate the integration.</li>
          <li><strong>Telegram connection information:</strong> connected bot identifier, username, webhook health and encrypted bot-token records used to route the business&apos;s Telegram conversations.</li>
          <li><strong>Customer and conversation information:</strong> customer phone numbers, profile names, messages, voice notes, supported media and conversation state used to understand and respond to requests.</li>
          <li><strong>Order information:</strong> products, quantities, delivery addresses and times, special instructions, invoices, payments where recorded, fulfilment status and customer requests.</li>
          <li><strong>Technical information:</strong> webhook events, provider message IDs, delivery/read/failure status, timestamps, audit records, diagnostics and security logs used for reliability and fraud prevention.</li>
          <li><strong>AI results:</strong> transcripts, intent classifications, structured extraction results, confidence indicators and corrections used to create reviewable business records.</li>
          <li><strong>Catalogue information:</strong> products, prices, units, aliases, availability and business-specific terminology used to improve order accuracy.</li>
        </ul>
      </section>

      <section>
        <h2>3. Why we use information</h2>
        <p>We use information to provide and secure PhoneERP, connect authorised business channels, receive and route messages, transcribe supported audio, extract structured order details, let owners review orders, coordinate packing and delivery, send operational notifications, provide customer tracking and invoices, troubleshoot failures, prevent duplicate processing, support users and comply with applicable law.</p>
        <p>PhoneERP does not sell customer or business personal information. Businesses must only connect accounts and process customer information when they have authority and an appropriate legal basis to do so.</p>
      </section>

      <section>
        <h2>4. Service providers</h2>
        <p>Depending on the enabled features, information may be processed by:</p>
        <ul>
          <li><strong>Meta:</strong> WhatsApp Business Platform messaging, media and webhook delivery.</li>
          <li><strong>Telegram:</strong> Telegram Bot API messaging, supported media and webhook delivery when a business connects its bot.</li>
          <li><strong>Render:</strong> backend application hosting and operational logs.</li>
          <li><strong>Supabase:</strong> authentication, database and application data storage.</li>
          <li><strong>Vercel:</strong> web application hosting and delivery.</li>
          <li><strong>AI and speech providers:</strong> configured providers such as Google Gemini and Sarvam AI for classification, extraction or transcription.</li>
          <li><strong>Optional communication providers:</strong> Twilio when a business enables supported telephony or sandbox messaging features.</li>
        </ul>
        <p>These providers process information under their own terms and privacy commitments. PhoneERP shares only the information reasonably needed to provide the configured feature.</p>
      </section>

      <section>
        <h2>5. Retention</h2>
        <ul>
          <li>Active workspace, catalogue, customer, message, order and integration records are retained while the business account remains active or until an authorised deletion request is completed.</li>
          <li>Operational and security logs may be retained for up to 180 days for troubleshooting, abuse prevention and audit purposes.</li>
          <li>After a verified account-deletion request, eligible live-system data is targeted for deletion within 30 days. Residual encrypted backups may take up to 90 additional days to expire.</li>
          <li>Invoices, transaction records or dispute evidence may be retained longer where required by applicable tax, accounting, fraud-prevention or legal obligations.</li>
        </ul>
      </section>

      <section>
        <h2>6. Security</h2>
        <p>PhoneERP uses role-based access controls, tenant-level data separation, HTTPS, webhook-signature verification, restricted server-side secrets, encrypted connected-business tokens, duplicate-message controls, logging and least-privilege access practices. No internet service can guarantee absolute security, so suspected incidents should be reported immediately through the support page.</p>
      </section>

      <section>
        <h2>7. Your choices and rights</h2>
        <p>Business owners may request access, correction, export, disconnection or deletion of eligible business data. Customers may ask the business they ordered from to correct or delete their information, or contact PhoneERP with enough information to identify the responsible business. We may need to verify identity and authority before acting.</p>
        <p>See the <a href="/data-deletion">Data Deletion Instructions</a> for the current request process.</p>
      </section>

      <section>
        <h2>8. International processing and policy changes</h2>
        <p>Providers may process information in countries other than the user&apos;s location. We will update this policy when our services, providers or legal obligations materially change and will publish the revised date on this page.</p>
      </section>
    </PublicPageShell>
  );
}
