type RestaurantItem = {
  size_variant?: unknown;
  add_ons?: unknown;
  spice_level?: unknown;
  veg_non_veg?: unknown;
  metadata?: Record<string, unknown>;
};

export function restaurantItemDetails(item: RestaurantItem): string[] {
  const metadata = item.metadata || {};
  const value = (key: keyof RestaurantItem) => item[key] ?? metadata[key];
  const details: string[] = [];

  for (const key of ['size_variant', 'spice_level', 'veg_non_veg'] as const) {
    const field = value(key);
    if (typeof field === 'string' && field.trim()) details.push(field.trim());
  }

  const addOns = value('add_ons');
  if (Array.isArray(addOns) && addOns.length) {
    details.push('Add-ons: ' + addOns.map(String).join(', '));
  }
  return details;
}

export function fulfillmentLabel(value?: string): string | null {
  if (!value || value === 'not_specified' || value === 'Not Specified') return null;
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
