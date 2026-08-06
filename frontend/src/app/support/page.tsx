import type { Metadata } from 'next';
import { Clock, Mail, ShieldAlert, Unplug } from 'lucide-react';
import PublicPageShell from '@/components/public/PublicPageShell';
import { publicSite } from '@/lib/public-site';

export const metadata: Metadata = {
  title: 'Support',
  description: 'Contact PhoneERP support, report a security concern or request WhatsApp disconnection.',
};

export default function SupportPage() {
  return (
    <PublicPageShell
      eyebrow="Help"
      title="PhoneERP Support"
      summary="Get help with business onboarding, connected channels, account access, order workflows, privacy or security concerns."
    >
      <div className="not-prose grid gap-4 sm:grid-cols-2">
        <div className="rounded-md border border-slate-300 bg-white p-5">
          <Mail className="h-5 w-5 text-indigo-700" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-bold">Email support</h2>
          <a href={`mailto:${publicSite.contactEmail}?subject=${encodeURIComponent('PhoneERP support request')}`} className="mt-2 block break-all text-sm font-semibold text-indigo-700 hover:underline">{publicSite.contactEmail}</a>
          <p className="mt-2 text-sm leading-6 text-slate-600">This inbox is monitored during support hours.</p>
        </div>
        <div className="rounded-md border border-slate-300 bg-white p-5">
          <Clock className="h-5 w-5 text-indigo-700" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-bold">Support hours</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{publicSite.supportHours}.</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">Expected first response: {publicSite.supportResponseTime}.</p>
        </div>
      </div>

      <section>
        <h2>For faster support</h2>
        <p>Include your registered business name, PhoneERP account email, affected channel, approximate incident time, order or message reference and a clear description. Screenshots are helpful, but redact access tokens, app secrets, OTPs, passwords, full payment details and customer information not needed for the issue.</p>
      </section>

      <section>
        <h2>Disconnect WhatsApp</h2>
        <div className="not-prose mt-4 flex gap-3 rounded-md border border-slate-300 bg-white p-4">
          <Unplug className="mt-0.5 h-5 w-5 shrink-0 text-indigo-700" aria-hidden="true" />
          <div className="text-sm leading-6 text-slate-700">
            <p>Email from the registered owner account with the business name, connected WhatsApp number and the words <strong>Disconnect WhatsApp</strong>.</p>
            <p className="mt-2">We verify ownership, disable PhoneERP processing, unsubscribe the integration where applicable and confirm the result. This does not delete the business-owned Meta account.</p>
          </div>
        </div>
      </section>

      <section>
        <h2>Report a privacy or security issue</h2>
        <div className="not-prose mt-4 flex gap-3 rounded-md border border-red-200 bg-red-50 p-4">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-red-700" aria-hidden="true" />
          <div className="text-sm leading-6 text-slate-700">
            <p>Email <a href={`mailto:${publicSite.contactEmail}?subject=${encodeURIComponent('Urgent PhoneERP security or privacy report')}`} className="font-semibold text-red-700 hover:underline">{publicSite.contactEmail}</a> with <strong>Security</strong> or <strong>Privacy</strong> in the subject.</p>
            <p className="mt-2">Describe what happened, when it occurred, the affected business and safe reproduction steps. Do not include live credentials. For an active account compromise, revoke exposed provider credentials and contact Meta or the affected provider immediately.</p>
          </div>
        </div>
      </section>

      <section>
        <h2>Deletion requests</h2>
        <p>Use the documented process on the <a href="/data-deletion">Data Deletion Instructions</a> page. Support requests do not automatically delete data.</p>
      </section>
    </PublicPageShell>
  );
}
