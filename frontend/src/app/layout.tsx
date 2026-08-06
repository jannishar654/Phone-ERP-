import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import LayoutWrapper from "@/components/common/LayoutWrapper";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://phone-erp.vercel.app"),
  title: { default: "PhoneERP | Conversational Order Operations", template: "%s | PhoneERP" },
  description: "Turn WhatsApp messages and voice notes into reviewable orders, fulfilment workflows, customer tracking and invoices.",
  openGraph: {
    title: "PhoneERP",
    description: "Conversational orders, structured into real operations.",
    url: "https://phone-erp.vercel.app",
    siteName: "PhoneERP",
    type: "website",
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
