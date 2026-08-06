import { notFound, redirect } from 'next/navigation';
import DocsShell from '@/components/public/DocsShell';

type Doc = { title: string; summary: string; sections: Array<{ title: string; paragraphs: string[]; bullets?: string[] }> };
const docs: Record<string, Doc> = {
  '': { title: 'Documentation', summary: 'Understand PhoneERP from customer message to completed order.', sections: [
    { title: 'What PhoneERP does', paragraphs: ['PhoneERP turns customer text and voice messages into organised orders. The owner checks every order before it moves to packing, delivery, customer tracking and billing.'], bullets: ['Accept text and voice orders', 'Review and correct order details', 'Use catalog prices and units', 'Coordinate packing and delivery', 'Share order progress and bills'] },
    { title: 'How to use this guide', paragraphs: ['Start with Getting started, then add your catalog and connect an order channel. The remaining sections explain the daily workflow for owners, packing staff, delivery staff and customers.'] },
    { title: 'Current availability', paragraphs: ['PhoneERP is being tested with real business workflows. Grocery ordering is the most established experience. Restaurant ordering and onboarding more businesses are still being improved through controlled pilots.'] },
  ] },
  'getting-started': { title: 'Getting started', summary: 'A practical sequence for setting up a PhoneERP workspace.', sections: [
    { title: 'Set up the business', paragraphs: ['Create an owner account, choose the business type and add the products or dishes you sell. Invite packing or delivery staff only when those roles are needed.'], bullets: ['Add the business name', 'Choose the business type', 'Add products, prices and units', 'Invite staff', 'Connect Telegram or another available order channel'] },
    { title: 'Receive orders', paragraphs: ['Customer orders can arrive through a connected messaging channel. Phone, counter and walk-in orders can be entered from New Order. Every order waits for the owner to check and approve it.'] },
    { title: 'Enter an order yourself', paragraphs: ['Open New Order. Type, paste or speak what the customer ordered, then check the customer name, items, quantity, unit, price, address and required time. Select Save order for review when everything is correct.'] },
    { title: 'Test your first order', paragraphs: ['Use a realistic order from your own business. Check that the correct item, quantity, price, address and time appear before approval. Then move it through packing, delivery and the customer bill.'] },
  ] },
  catalog: { title: 'Catalog setup', summary: 'Teach PhoneERP the products, prices, units and names customers actually use.', sections: [
    { title: 'Add products or dishes', paragraphs: ['Add the name customers use, selling price and correct unit for every product or dish.'], bullets: ['Use units such as kg, plate, piece or litre', 'Keep prices up to date', 'Mark unavailable items inactive', 'Add restaurant sizes and portions carefully'] },
    { title: 'Add other names customers use', paragraphs: ['Customers may use Hindi, Hinglish, short names or local names. Add these as alternate names so, for example, atta can match the correct flour product.'] },
    { title: 'Check before going live', paragraphs: ['Try a few real customer-style messages. Check the item, quantity, unit and total before approving each order.'] },
  ] },
  channels: { title: 'Order channels', summary: 'Connect customer conversations without building a separate order system for every provider.', sections: [
    { title: 'One order process', paragraphs: ['Orders from connected channels follow the same owner review, packing, delivery, tracking and billing process. Staff do not need a different dashboard for each channel.'] },
    { title: 'Available connections', paragraphs: ['A business can connect its own Telegram bot. WhatsApp is available for PhoneERP’s connected number and selected assisted pilots while easier multi-business onboarding is being completed. Twilio remains available for existing pilot setups.'] },
    { title: 'Keep business accounts safe', paragraphs: ['The business should own its phone number or bot. Only the owner should connect or disconnect an account, and secret tokens should never be shared in chat or documentation.'] },
  ] },
  whatsapp: { title: 'WhatsApp integration', summary: 'How official WhatsApp messages enter PhoneERP and remain isolated by business.', sections: [
    { title: 'How WhatsApp orders work', paragraphs: ['A customer sends a text or voice message to the connected business number. PhoneERP sends the order to the correct business and prepares it for owner review. Repeated delivery of the same message does not create another order.'] },
    { title: 'Connecting a business number', paragraphs: ['WhatsApp setup is currently assisted by the PhoneERP team. Connecting many businesses through a self-service button is still being prepared with Meta. Do not move a business’s main number until eligibility, access and recovery have been confirmed.'] },
  ] },
  telegram: { title: 'Telegram integration', summary: 'Connect a separate Telegram bot to each PhoneERP business.', sections: [
    { title: 'Create and connect a bot', paragraphs: ['Create a bot with @BotFather, then open PhoneERP Settings, Integrations and Telegram. Paste the bot token into the owner-only form and confirm the bot name shown by PhoneERP.'], bullets: ['Create one bot for the business', 'Connect it from the owner account', 'Send a test order', 'Disconnect and reconnect if the token changes'] },
    { title: 'One bot per business', paragraphs: ['Each connected bot sends orders only to its own PhoneERP business. A customer who messages one business bot cannot see another business’s orders or data.'] },
    { title: 'Need help connecting?', paragraphs: ['Ask the PhoneERP team for setup help. Do not send the bot token through WhatsApp, email screenshots or public messages.'] },
  ] },
  'business-configuration': { title: 'Business configuration', summary: 'Adapt extraction without creating a separate ERP for every industry.', sections: [
    { title: 'Business-specific setup', paragraphs: ['PhoneERP can use the words, units and order details that matter to each business.'], bullets: ['Grocery quantities and units', 'Restaurant portions and dietary notes', 'Bakery variants and required dates', 'Local product names and sizes'] },
    { title: 'Existing grocery businesses', paragraphs: ['Existing grocery businesses continue using the current grocery setup unless the owner chooses a different business configuration.'] },
  ] },
  'order-lifecycle': { title: 'Order lifecycle', summary: 'The states that keep owners and fulfilment staff aligned.', sections: [
    { title: 'Order stages', paragraphs: ['A new request waits for the owner to check it. After approval, staff can prepare and deliver it.'], bullets: ['Received', 'Approved and packing', 'Out for delivery', 'Delivered or cancelled'] },
    { title: 'Customer updates', paragraphs: ['PhoneERP sends available status and bill updates through the customer’s order channel. If an update fails, the order status remains saved and the owner can retry the message.'] },
  ] },
  'customer-portal': { title: 'Customer portal', summary: 'A private, read-focused view of the customer’s orders.', sections: [
    { title: 'Private order link', paragraphs: ['Customers receive a private link showing their order items, total, delivery information and current progress. They do not need an owner account.'] },
    { title: 'Editing an order', paragraphs: ['A customer can correct an order while it is still waiting for owner approval. After approval, they must contact the business for any change.'] },
  ] },
  'roles-and-permissions': { title: 'Roles and permissions', summary: 'Keep each user inside the correct shop and workflow.', sections: [
    { title: 'Owner', paragraphs: ['Owners manage action cards, orders, catalog, customer requests, integrations and staff access.'] },
    { title: 'Packing and delivery staff', paragraphs: ['Packing staff see orders that are ready to prepare. Delivery staff see orders that are ready to deliver. Staff only see work for the business they joined.'] },
  ] },
  troubleshooting: { title: 'Troubleshooting', summary: 'A short checklist for common setup and order-processing problems.', sections: [
    { title: 'A new order is not visible', paragraphs: ['Refresh the Action Cards page and confirm the customer messaged the correct connected number or bot. Open Integration Settings to check whether the connection is active.'] },
    { title: 'The item, unit or price is wrong', paragraphs: ['Edit the order before approval. Then correct the product name, alternate name, unit or price in Catalog so future orders match correctly.'] },
    { title: 'Telegram does not reply', paragraphs: ['Open Settings, Integrations and Telegram. Test the connection. If the bot token was changed or shared, disconnect the bot and connect it again with a new token.'] },
    { title: 'The customer did not receive an update', paragraphs: ['Confirm the customer phone number or chat is correct, then try the update again. The saved order and delivery status are not removed when a message fails.'] },
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
