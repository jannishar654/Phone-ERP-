import EditorialPage from '@/components/public/EditorialPage';

const businesses = [
  {
    title: 'Grocery',
    description: 'Quantity, unit, aliases, delivery address, delivery time and catalogue pricing.',
    status: 'Available',
    statusClass: 'is-live',
  },
  {
    title: 'Restaurant',
    description: 'Menu items, portions, spice level, dietary notes, fulfilment type and delivery timing.',
    status: 'Guided pilot',
    statusClass: 'is-pilot',
  },
  {
    title: 'Wholesale',
    description: 'Bulk quantities, negotiated units, delivery scheduling and customer-specific ordering terms.',
    status: 'Planned',
    statusClass: 'is-planned',
  },
  {
    title: 'Bakery, pharmacy and general trade',
    description: 'Configuration research exists, but these workflows are not yet offered as production-ready onboarding options.',
    status: 'Planned',
    statusClass: 'is-planned',
  },
];

export default function BusinessesPage() {
  return (
    <EditorialPage
      eyebrow="Businesses"
      title="A shared platform, adapted to each business workflow."
      summary="PhoneERP keeps one order engine while allowing terminology, required fields and operational stages to evolve by business type."
    >
      <section className="public-section">
        <div className="public-container public-panel">
          {businesses.map((business, index) => (
            <div className="public-info-row public-business-row" key={business.title}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <div>
                <div className="public-business-title">
                  <h2>{business.title}</h2>
                  <small className={`public-availability ${business.statusClass}`}>{business.status}</small>
                </div>
                <p>{business.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="public-section">
        <div className="public-container public-feature-split public-grid-2">
          <div>
            <p className="public-kicker">Configuration, not forks</p>
            <h2>New business types should not require a separate ERP.</h2>
          </div>
          <div className="public-copy">
            <p>A shop configuration supplies its terminology, required fields, extraction context and lifecycle. The core message, review, order and notification pipeline remains shared.</p>
            <p>Grocery is the production baseline. Restaurant support remains a guided pilot while menu, fulfilment and dietary workflows are validated.</p>
          </div>
        </div>
      </section>
    </EditorialPage>
  );
}
