import { notFound } from 'next/navigation';
import DocsShell from '@/components/public/DocsShell';

type Doc = { title: string; summary: string; sections: Array<{ title: string; paragraphs: string[]; bullets?: string[] }> };
const docs: Record<string, Doc> = {
  '': { title: 'Documentation', summary: 'Understand PhoneERP from customer message to completed order.', sections: [
    { title: 'What PhoneERP does', paragraphs: ['PhoneERP receives conversational requests, identifies customer intent, extracts structured order details and sends the result to an owner for review.'], bullets: ['Text and voice-note intake', 'Editable action cards', 'Packing and delivery workspaces', 'Customer tracking and invoices', 'Configurable business terminology'] },
    { title: 'Product maturity', paragraphs: ['The current system is a working production prototype. Core grocery operations are established, restaurant configuration is being validated, and scalable WhatsApp onboarding remains an active milestone.'] },
  ] },
  'getting-started': { title: 'Getting started', summary: 'A practical sequence for setting up a PhoneERP workspace.', sections: [
    { title: 'Owner setup', paragraphs: ['Create an owner account, select the business type and confirm the shop workspace. Existing shops without a configuration retain grocery defaults.'], bullets: ['Create or confirm the shop', 'Review business configuration', 'Add catalog items and aliases', 'Invite packing or delivery staff', 'Connect a messaging channel'] },
    { title: 'First order test', paragraphs: ['Send a realistic customer message, confirm that an action card appears, edit any incorrect field, approve it, and move the resulting order through packing and delivery.'] },
  ] },
  whatsapp: { title: 'WhatsApp integration', summary: 'How official WhatsApp messages enter PhoneERP and remain isolated by business.', sections: [
    { title: 'Message path', paragraphs: ['Meta sends webhook events to one shared backend endpoint. PhoneERP verifies the signature, reads the phone-number ID, resolves the correct shop and normalizes the message before processing.'], bullets: ['Never trust a tenant ID from the browser', 'Store message IDs for deduplication', 'Keep access tokens on the backend', 'Use official Cloud API or an approved provider'] },
    { title: 'Business onboarding', paragraphs: ['A single owned production number is supported. Connecting unrelated businesses at scale requires Meta Business verification, Tech Provider setup, App Review, Advanced Access and Embedded Signup.'] },
  ] },
  'business-configuration': { title: 'Business configuration', summary: 'Adapt extraction without creating a separate ERP for every industry.', sections: [
    { title: 'Configuration fields', paragraphs: ['Each shop can define its business type, terminology, required fields, workflow stages, extraction context and settings.'], bullets: ['Grocery and wholesale units', 'Restaurant portions and dietary notes', 'Bakery variants and schedules', 'General trade aliases and dimensions'] },
    { title: 'Fallback behaviour', paragraphs: ['If an older shop has no stored configuration, PhoneERP uses the proven grocery defaults to protect existing production behaviour.'] },
  ] },
  'order-lifecycle': { title: 'Order lifecycle', summary: 'The states that keep owners and fulfilment staff aligned.', sections: [
    { title: 'Core stages', paragraphs: ['A customer request begins as an action card. After approval it becomes an operational order and progresses through fulfilment.'], bullets: ['Received and pending review', 'Approved and packing', 'Out for delivery', 'Delivered or cancelled'] },
    { title: 'Notifications', paragraphs: ['Delivery notifications are attempted after the status update succeeds. Provider failures remain visible but do not roll back the operational state.'] },
  ] },
  'customer-portal': { title: 'Customer portal', summary: 'A private, read-focused view of the customer’s orders.', sections: [
    { title: 'Access model', paragraphs: ['Customers receive a private link tied to their shop and identity. The portal shows order progress, line items and delivery information without an owner login.'] },
    { title: 'Editing', paragraphs: ['Pending drafts can expose controlled editing before owner approval. Approved orders remain protected from unsafe customer-side changes.'] },
  ] },
  'roles-and-permissions': { title: 'Roles and permissions', summary: 'Keep each user inside the correct shop and workflow.', sections: [
    { title: 'Owner', paragraphs: ['Owners manage action cards, orders, catalog, customer requests, integrations and staff access.'] },
    { title: 'Packer and delivery', paragraphs: ['Packers only access packing endpoints and delivery staff only access delivery endpoints. Both are scoped to an active shop membership.'], bullets: ['No cross-shop visibility', 'No owner fallback on staff endpoints', 'Role-specific lifecycle transitions'] },
  ] },
};

export default async function DocsPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const { slug: parts = [] } = await params;
  const slug = parts.join('/');
  const doc = docs[slug];
  if (!doc) notFound();
  return <DocsShell slug={slug} title={doc.title} summary={doc.summary}>{doc.sections.map((section) => <section key={section.title}><h2>{section.title}</h2>{section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}{section.bullets && <ul>{section.bullets.map((item) => <li key={item}>{item}</li>)}</ul>}</section>)}</DocsShell>;
}
