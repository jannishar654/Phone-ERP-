import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import LayoutWrapper from "@/components/common/LayoutWrapper";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://phone-erp.vercel.app"),
  title: { default: "PhoneERP | Conversational Order Operations", template: "%s | PhoneERP" },
  description: "Turn WhatsApp messages and voice notes into reviewable orders, fulfilment workflows, customer tracking and invoices.",
  applicationName: "PhoneERP",
  creator: "PhoneERP project team",
  publisher: "PhoneERP",
  category: "Business software",
  keywords: [
    "PhoneERP",
    "WhatsApp order management",
    "voice order automation",
    "small business ERP",
    "order fulfilment",
    "customer order tracking",
  ],
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    shortcut: "/favicon.ico",
  },
  openGraph: {
    title: "PhoneERP | Conversational Order Operations",
    description: "Turn customer text and voice messages into reviewable orders, fulfilment workflows, tracking and invoices.",
    url: "https://phone-erp.vercel.app",
    siteName: "PhoneERP",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "PhoneERP turns conversational orders into structured business operations",
      },
    ],
    locale: "en_IN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "PhoneERP | Conversational Order Operations",
    description: "Turn customer text and voice messages into reviewable orders, fulfilment workflows, tracking and invoices.",
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className={`${inter.className} min-h-full`}>
        <LayoutWrapper>{children}</LayoutWrapper>
      </body>
    </html>
  );
}
