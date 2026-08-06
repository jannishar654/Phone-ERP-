import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'PhoneERP | Conversational Order Operations',
    short_name: 'PhoneERP',
    description: 'Turn customer text and voice messages into reviewable orders, fulfilment workflows, tracking and invoices.',
    start_url: '/',
    display: 'standalone',
    background_color: '#08090a',
    theme_color: '#08090a',
    icons: [
      {
        src: '/icon.svg',
        sizes: 'any',
        type: 'image/svg+xml',
      },
    ],
  };
}
