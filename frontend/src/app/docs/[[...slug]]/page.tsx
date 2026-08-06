import { notFound, redirect } from 'next/navigation';
import DocsShell from '@/components/public/DocsShell';

type Doc = { title: string; summary: string; sections: Array<{ title: string; paragraphs: string[]; bullets?: string[] }> };
const docs: Record<string, Doc> = {
  '': { title: 'Documentation', summary: 'Understand PhoneERP from customer message to completed order.', sections: [
    { title: 'What PhoneERP does', paragraphs: ['PhoneERP receives conversational requests, identifies customer intent, extracts structured order details and sends the result to an owner for review. The same operational pipeline is reused across supported channels.'], bullets: ['Text and voice-note intake', 'Editable action cards', 'Catalog-aware pricing', 'Packing and delivery workspaces', 'Customer tracking and invoices', 'Configurable business terminology'] },
    { title: 'Choose a guide', paragraphs: ['Start with Getting started for a first workspace. Use Catalog setup to improve item matching, Order channels to compare integrations, and the provider guides to connect WhatsApp or Telegram.'] },
    { title: 'Product maturity', paragraphs: ['The current system is a working production prototype. Core grocery operations are established, restaurant configuration is being validated, per-business Telegram bots are available after deployment setup, and scalable WhatsApp Embedded Signup remains an active milestone.'] },
  ] },
  'getting-started': { title: 'Getting started', summary: 'A practical sequence for setting up a PhoneERP workspace.', sections: [
    { title: 'Owner setup', paragraphs: ['Create an owner account, select the business type and confirm the shop workspace. Existing shops without a configuration retain grocery defaults.'], bullets: ['Create or confirm the shop', 'Review business configuration', 'Add catalog items and aliases', 'Invite packing or delivery staff', 'Connect a messaging channel'] },
    { title: 'Two professional order paths', paragraphs: ['Automatic orders arrive through a connected channel such as WhatsApp or Telegram. Phone, walk-in and offline orders are entered by the owner from New Order. Both paths create a pending Action Card and use the same review, approval, packing, delivery, tracking and billing workflow.'], bullets: ['Automatic: customer message or voice note to pending Action Card', 'Owner-assisted: New Order form to pending Action Card', 'No channel-specific fulfilment system', 'Owner approval remains the control point'] },
    { title: 'Create an owner-assisted order', paragraphs: ['Open New Order, enter the customer and fulfilment details, then add products from the business catalog. For a faster draft, paste call notes or record a short voice note and use AI assist to prefill the form. Nothing is saved until the owner reviews the fields and selects Create Action Card.'] },
    { title: 'First order test', paragraphs: ['Test both paths. Send one realistic customer message, then create one phone or walk-in order from New Order. Confirm that each Action Card can be corrected before approval and that both resulting orders progress through packing and delivery.'] },
  ] },
  catalog: { title: 'Catalog setup', summary: 'Teach PhoneERP the products, prices, units and names customers actually use.', sections: [
    { title: 'Add sellable items', paragraphs: ['Create each product with its customer-facing name, price, supported unit and active status. Accurate catalog data lets PhoneERP calculate totals and gives the owner a reliable review surface.'], bullets: ['Use the exact selling unit, such as kg, plate, piece or litre', 'Keep prices current', 'Deactivate unavailable items instead of deleting history', 'Review restaurant portions and variants before a pilot'] },
    { title: 'Add aliases', paragraphs: ['Aliases connect informal Hindi, Hinglish, abbreviations and local product names to one catalog item. For example, atta and aashirvaad flour can resolve to the same product when that mapping is intended by the business.'] },
    { title: 'Test before real orders', paragraphs: ['Send several realistic messages with spelling variations, mixed languages and missing details. Confirm the action card item, quantity, unit and total before approving it.'] },
  ] },
  channels: { title: 'Order channels', summary: 'Connect customer conversations without building a separate order system for every provider.', sections: [
    { title: 'Shared processing pipeline', paragraphs: ['WhatsApp, Telegram and supported voice-note sources are normalized before intent detection and extraction. Orders then use the same action-card, catalog, fulfilment and customer-notification workflow.'] },
    { title: 'Current channel status', paragraphs: ['Telegram supports a separate BotFather bot per business after the database migration and backend configuration. Meta WhatsApp supports the owned production connection and assisted pilots; self-service onboarding for unrelated businesses still requires Embedded Signup and Meta approvals. Twilio remains a supported legacy pilot path.'] },
    { title: 'Provider ownership', paragraphs: ['A business should own its messaging account, number or bot. Provider tokens must only be stored by the backend and must never be pasted into browser code, Vercel variables or public documentation.'] },
  ] },
  whatsapp: { title: 'WhatsApp integration', summary: 'How official WhatsApp messages enter PhoneERP and remain isolated by business.', sections: [
    { title: 'Message path', paragraphs: ['Meta sends webhook events to one shared backend endpoint. PhoneERP verifies the signature, reads the phone-number ID, resolves the correct shop and normalizes the message before processing.'], bullets: ['Never trust a tenant ID from the browser', 'Store message IDs for deduplication', 'Keep access tokens on the backend', 'Use official Cloud API or an approved provider'] },
    { title: 'Business onboarding', paragraphs: ['A single owned production number is supported. Connecting unrelated businesses at scale requires Meta Business verification, Tech Provider setup, App Review, Advanced Access and Embedded Signup.'] },
  ] },
  telegram: { title: 'Telegram integration', summary: 'Connect a separate Telegram bot to each PhoneERP business.', sections: [
    { title: 'Create the business bot', paragraphs: ['The owner creates a bot with BotFather, copies the bot token once, and opens PhoneERP Settings, Integrations, Telegram. PhoneERP validates the token, registers a unique webhook and stores the credential encrypted on the backend.'], bullets: ['Create the bot with @BotFather', 'Copy the token into the owner-only connection form', 'Confirm the bot username shown by PhoneERP', 'Send a test order to the bot', 'Disconnect or rotate the bot if the token is exposed'] },
    { title: 'Tenant routing', paragraphs: ['Each webhook URL contains a random PhoneERP connection identifier and uses a separate secret header. The backend resolves the shop from the stored connection; it never trusts a shop ID supplied by Telegram or the browser.'] },
    { title: 'Deployment requirements', paragraphs: ['Run migration 026_multi_business_telegram.sql, configure TELEGRAM_WEBHOOK_BASE_URL with the public Render backend origin, and keep the integration encryption key stable across deployments. Generate it once with the command below, save the resulting value only in Render as INTEGRATION_CREDENTIAL_ENCRYPTION_KEY, and never commit it.'], bullets: ["Generate a key: openssl rand -base64 32 | tr '+/' '-_'", 'Keep the same key across every redeploy', 'Back it up in an approved password or secrets manager', 'Do not rotate it until a credential re-encryption workflow exists', 'The legacy environment bot remains available for backward compatibility'] },
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
  troubleshooting: { title: 'Troubleshooting', summary: 'A short checklist for common setup and order-processing problems.', sections: [
    { title: 'No action card appears', paragraphs: ['Confirm the provider webhook returns HTTP 200, the connection is active for the expected shop, the incoming message ID is new, and the business catalog contains the requested product. Then inspect Render logs without exposing message bodies or tokens.'] },
    { title: 'Incorrect item, unit or price', paragraphs: ['Correct the action card before approval, then update catalog aliases, units or prices so the next request resolves consistently. Do not force unsupported restaurant orders through grocery defaults.'] },
    { title: 'Telegram does not reply', paragraphs: ['Run the Telegram connection health check, confirm the webhook base URL is HTTPS, verify migration 026 has been applied, and reconnect the bot if BotFather rotated its token.'] },
    { title: 'Notification fails after delivery', paragraphs: ['The operational status remains delivered even when a provider notification fails. Check the response notification fields and backend provider logs, then retry through the correct business channel.'] },
  ] },
};

export default async function DocsPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const { slug: parts = [] } = await params;
  const slug = parts.join('/');
  if (slug && !docs[slug]) notFound();

  const chapterId = (path: string) => `docs-${path || 'overview'}`;
  if (slug) redirect(`/docs#${chapterId(slug)}`);

  const entries = Object.entries(docs);
  const chapters = entries.map(([path, doc]) => ({
    id: chapterId(path),
    path,
    title: path ? doc.title : 'Overview',
  }));

  return (
    <DocsShell
      title="Documentation"
      summary="Follow PhoneERP from first workspace setup through integrations, fulfilment and troubleshooting."
      chapters={chapters}
    >
      {entries.map(([path, doc], chapterIndex) => (
        <section className="docs-chapter" id={chapterId(path)} key={path || 'overview'}>
          <div className="docs-chapter-heading">
            <p>{String(chapterIndex + 1).padStart(2, '0')}</p>
            <h2>{path ? doc.title : 'Overview'}</h2>
            <p>{doc.summary}</p>
          </div>
          <div className="docs-chapter-topics">
            {doc.sections.map((section) => (
              <section className="docs-topic" key={section.title}>
                <h3>{section.title}</h3>
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
                {section.bullets && <ul>{section.bullets.map((item) => <li key={item}>{item}</li>)}</ul>}
              </section>
            ))}
          </div>
        </section>
      ))}
    </DocsShell>
  );
}
