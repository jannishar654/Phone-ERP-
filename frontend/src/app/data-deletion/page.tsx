import type { Metadata } from 'next';
import { Mail, Unplug } from 'lucide-react';
import PublicPageShell from '@/components/public/PublicPageShell';
import { publicSite } from '@/lib/public-site';

export const metadata: Metadata = {
  title: 'Data Deletion Instructions',
  description: 'How businesses and customers can request disconnection and deletion of eligible PhoneERP data.',
};

const deletionMailto = `mailto:${publicSite.contactEmail}?subject=${encodeURIComponent('PhoneERP account and data deletion request')}`;

export default function DataDeletionPage() {
  return (
    <PublicPageShell
      eyebrow="Privacy request"
      title="Data Deletion Instructions"
      summary="Businesses and customers can request deletion of eligible PhoneERP information. We verify requests to prevent unauthorised deletion."
    >
      <section>
        <h2>Request deletion by email</h2>
        <p>Email <a href={deletionMailto}>{publicSite.contactEmail}</a> with the subject <strong>PhoneERP account and data deletion request</strong>.</p>
        <p>For a business-account request, include:</p>
        <ul>
          <li>Registered business name.</li>
          <li>PhoneERP account email.</li>
          <li>Connected WhatsApp number, including country code.</li>
          <li>Whether you want WhatsApp disconnected, eligible data deleted, or both.</li>
        </ul>
        <a href={deletionMailto} className="not-prose mt-5 inline-flex min-h-11 items-center gap-2 rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-indigo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2">
          <Mail className="h-4 w-4" aria-hidden="true" /> Email deletion request
        </a>
      </section>

      <section>
        <h2>What happens next</h2>
        <ol>
          <li>We acknowledge the request and may ask for information needed to verify the requester&apos;s identity and authority.</li>
          <li>After verification, we disconnect the requested WhatsApp integration and revoke or remove PhoneERP&apos;s stored connection credentials.</li>
          <li>We delete eligible business, customer, conversation, message, voice-note, order and integration information from active systems, normally within 30 days.</li>
          <li>Encrypted backups may retain residual copies for up to 90 additional days. Records required for tax, fraud prevention, disputes or legal compliance may be retained for the required period.</li>
          <li>We send confirmation when the live-system deletion is completed or explain any information that cannot yet be deleted.</li>
        </ol>
      </section>

      <section>
        <h2>Customer requests</h2>
        <p>If you placed an order with a business using PhoneERP, contact that business first because it controls the customer relationship and can identify your records. You may also email us with your phone number, the business name and a description of the information involved. Do not send passwords, OTPs, payment-card information or Meta access tokens.</p>
      </section>

      <section>
        <h2>Disconnect without deleting the Meta account</h2>
        <div className="not-prose mt-4 flex gap-3 rounded-md border border-slate-300 bg-white p-4">
          <Unplug className="mt-0.5 h-5 w-5 shrink-0 text-indigo-700" aria-hidden="true" />
          <p className="text-sm leading-6 text-slate-700">A verified owner may ask us to disconnect PhoneERP while keeping the business&apos;s Meta Business Portfolio, WABA and phone number under the business&apos;s ownership.</p>
        </div>
        <p><strong>Planned dashboard controls:</strong> Settings &rarr; WhatsApp &rarr; Disconnect WhatsApp and Settings &rarr; Account &rarr; Delete account. Until those controls are released, the verified email process above is the supported method.</p>
      </section>
    </PublicPageShell>
  );
}
