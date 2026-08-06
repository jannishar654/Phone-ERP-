import EditorialPage from '@/components/public/EditorialPage';

const businesses = [
  ['Grocery and wholesale', 'Quantity, unit, aliases, delivery address, delivery time and catalog pricing.'],
  ['Restaurants', 'Menu items, portions, spice level, dietary notes, fulfilment type and delivery timing.'],
  ['Bakery', 'Variants, message-on-cake details, delivery date and advance-order requirements.'],
  ['Pharmacy', 'Product requests and fulfilment routing, with human review for sensitive or regulated cases.'],
  ['Hardware and general trade', 'Item aliases, dimensions, quantities, unit types and delivery instructions.'],
];

export default function BusinessesPage() {
  return (
    <EditorialPage eyebrow="Businesses" title="One platform. Configurable business language." summary="PhoneERP keeps a unified order engine while adapting terminology, required fields and workflow stages for each business.">
      <section className="public-section"><div className="public-container public-panel">
        {businesses.map(([title, text], index) => <div className="public-info-row" key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><h2>{title}</h2><p>{text}</p></div></div>)}
      </div></section>
      <section className="public-section"><div className="public-container public-feature-split public-grid-2"><div><p className="public-kicker">Configuration, not forks</p><h2>New business types should not require a separate ERP.</h2></div><div className="public-copy"><p>A shop configuration supplies its terminology, required fields, extraction context and lifecycle. The core message, review, order and notification pipeline remains shared.</p><p>Grocery is the production baseline. Restaurant support is being validated without changing the proven grocery behaviour.</p></div></div></section>
    </EditorialPage>
  );
}
