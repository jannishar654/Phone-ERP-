import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Headphones,
  LockKeyhole,
  MessageCircle,
  PackageCheck,
  Send,
  Settings2,
  ShoppingBasket,
  Store,
  Truck,
  Users,
} from "lucide-react";

const sections = [
  ["overview", "Overview"],
  ["quick-start", "Quick start"],
  ["catalog", "Catalog setup"],
  ["channels", "Order channels"],
  ["workflow", "Order workflow"],
  ["customers", "Customer experience"],
  ["roles", "Team roles"],
  ["business-types", "Business types"],
  ["security", "Security"],
  ["troubleshooting", "Troubleshooting"],
] as const;

const featureCards = [
  {
    icon: MessageCircle,
    title: "Conversational intake",
    copy: "Receive text and voice-note orders, classify customer intent, and collect missing profile or delivery details.",
  },
  {
    icon: ClipboardCheck,
    title: "Owner review",
    copy: "Turn extracted requests into editable Action Cards before anything enters fulfilment.",
  },
  {
    icon: PackageCheck,
    title: "Operations",
    copy: "Move approved orders through packing, out for delivery, delivery, and cancellation states.",
  },
  {
    icon: FileText,
    title: "Customer records",
    copy: "Provide order tracking, customer requests, delivery updates, and public bill links without exposing the owner workspace.",
  },
] as const;

function SectionTitle({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="max-w-3xl">
      <p className="text-xs font-bold uppercase text-amber-700">{eyebrow}</p>
      <h2 className="mt-2 text-2xl font-bold text-slate-950">{title}</h2>
      <p className="mt-3 leading-7 text-slate-600">{copy}</p>
    </div>
  );
}

function StatusLabel({ children, kind = "ready" }: { children: React.ReactNode; kind?: "ready" | "pilot" | "planned" }) {
  const styles = kind === "ready"
    ? "border-slate-300 bg-slate-100 text-slate-800"
    : kind === "pilot"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-slate-200 bg-white text-slate-500";
  return <span className={`inline-flex border px-2 py-1 text-xs font-bold uppercase ${styles}`}>{children}</span>;
}

export default function DocumentationPage() {
  return (
    <div className="min-h-screen bg-white text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-3" aria-label="PhoneERP home">
            <span className="flex h-9 w-9 items-center justify-center border border-slate-300 bg-slate-950 font-mono text-xs font-bold text-white">PE</span>
            <span className="font-bold">PhoneERP <span className="font-medium text-slate-400">Docs</span></span>
          </Link>
          <nav className="flex items-center gap-3" aria-label="Documentation actions">
            <Link href="/support" className="hidden text-sm font-semibold text-slate-600 hover:text-slate-950 sm:inline">Support</Link>
            <Link href="/login" className="bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">Open workspace</Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl lg:grid-cols-[230px_minmax(0,1fr)]">
        <aside className="hidden border-r border-slate-200 px-6 py-10 lg:block">
          <div className="sticky top-24">
            <p className="mb-4 text-xs font-bold uppercase text-slate-400">Product guide</p>
            <nav className="space-y-1" aria-label="On this page">
              {sections.map(([id, label]) => (
                <a key={id} href={`#${id}`} className="block border-l-2 border-transparent py-1.5 pl-3 text-sm text-slate-600 hover:border-slate-900 hover:text-slate-950">
                  {label}
                </a>
              ))}
            </nav>
          </div>
        </aside>

        <main className="min-w-0 px-4 py-10 sm:px-8 lg:px-12 lg:py-14">
          <section id="overview" className="scroll-mt-24 border-b border-slate-200 pb-14">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-700"><BookOpen className="h-4 w-4" /> Product documentation</div>
            <h1 className="mt-5 max-w-4xl text-4xl font-bold leading-tight text-slate-950 sm:text-5xl">Run conversational orders as a controlled business workflow.</h1>
            <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">
              PhoneERP converts customer messages and voice notes into structured order drafts, gives the owner a review step, coordinates packing and delivery, and keeps customers informed.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="inline-flex items-center gap-2 bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800">Create a business workspace <ArrowRight className="h-4 w-4" /></Link>
              <Link href="/support" className="inline-flex items-center gap-2 border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-100">Contact support</Link>
            </div>
            <div className="mt-10 grid gap-3 sm:grid-cols-2">
              {featureCards.map(({ icon: Icon, title, copy }) => (
                <article key={title} className="border border-slate-200 bg-slate-50 p-5">
                  <Icon className="h-5 w-5 text-slate-700" />
                  <h2 className="mt-4 font-bold text-slate-950">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{copy}</p>
                </article>
              ))}
            </div>
          </section>

          <section id="quick-start" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Getting started" title="Set up a usable workspace" copy="Complete these steps in order. A channel can receive messages before the catalog is complete, but accurate catalog matching and pricing depend on the business data." />
            <ol className="mt-8 divide-y divide-slate-200 border-y border-slate-200">
              {[
                ["01", "Create the owner account", "Choose the business type, enter the business name, and confirm the owner account."],
                ["02", "Prepare the catalog", "Add products, prices, units, aliases, and availability. Include Hindi or Hinglish names customers actually use."],
                ["03", "Connect an order channel", "Connect Telegram using a dedicated bot, or use an assisted WhatsApp/Twilio pilot configured by PhoneERP."],
                ["04", "Invite operational staff", "Generate role-specific access for packers and delivery staff. Owners continue to review Action Cards."],
                ["05", "Place and fulfil a test order", "Test profile collection, extraction, approval, packing, delivery, tracking, and the final bill before using real orders."],
              ].map(([number, title, copy]) => (
                <li key={number} className="grid gap-3 py-5 sm:grid-cols-[48px_220px_minmax(0,1fr)]">
                  <span className="font-mono text-sm font-bold text-amber-700">{number}</span>
                  <strong className="text-slate-900">{title}</strong>
                  <span className="text-sm leading-6 text-slate-600">{copy}</span>
                </li>
              ))}
            </ol>
          </section>

          <section id="catalog" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Business data" title="Build the catalog the AI can trust" copy="The catalog is the source for recognized products, display names, units, aliases, and prices. It reduces incorrect assumptions and keeps owner review meaningful." />
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              <div className="border border-slate-200 p-5">
                <ShoppingBasket className="h-5 w-5 text-slate-700" />
                <h3 className="mt-4 font-bold">Recommended product fields</h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  <li>Product name and customer-facing display name</li>
                  <li>Current unit price and selling unit</li>
                  <li>Aliases such as atta, aata, flour, or local spellings</li>
                  <li>Availability and business-specific notes</li>
                </ul>
              </div>
              <div className="border border-slate-200 p-5">
                <Store className="h-5 w-5 text-slate-700" />
                <h3 className="mt-4 font-bold">Operational rule</h3>
                <p className="mt-3 text-sm leading-6 text-slate-600">Review new aliases and price changes before live use. When an item cannot be matched safely, the order should stay pending for owner verification instead of inventing a product or price.</p>
              </div>
            </div>
          </section>

          <section id="channels" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Integrations" title="Choose how customers reach the business" copy="Every channel is normalized into the same PhoneERP order pipeline. Channel availability differs, so the current status is shown explicitly." />
            <div className="mt-8 overflow-hidden border border-slate-200">
              <div className="grid gap-3 border-b border-slate-200 p-5 md:grid-cols-[170px_120px_minmax(0,1fr)]">
                <div className="flex items-center gap-2 font-bold"><Send className="h-4 w-4" /> Telegram</div>
                <div><StatusLabel>Ready</StatusLabel></div>
                <div className="text-sm leading-6 text-slate-600">Each business creates a dedicated bot with <a className="font-semibold text-slate-950 underline" href="https://t.me/BotFather" target="_blank" rel="noreferrer">BotFather <ExternalLink className="inline h-3.5 w-3.5" /></a>, then pastes the token in <strong>Workspace → Telegram</strong>. PhoneERP validates the bot, encrypts the token, and configures its webhook automatically.</div>
              </div>
              <div className="grid gap-3 border-b border-slate-200 p-5 md:grid-cols-[170px_120px_minmax(0,1fr)]">
                <div className="flex items-center gap-2 font-bold"><MessageCircle className="h-4 w-4" /> WhatsApp</div>
                <div><StatusLabel kind="pilot">Assisted pilot</StatusLabel></div>
                <div className="text-sm leading-6 text-slate-600">The current PhoneERP Meta number and existing pilot connection can receive orders. Self-service onboarding for external businesses through Meta Embedded Signup is still under development and should not be presented as generally available.</div>
              </div>
              <div className="grid gap-3 p-5 md:grid-cols-[170px_120px_minmax(0,1fr)]">
                <div className="flex items-center gap-2 font-bold"><Headphones className="h-4 w-4" /> Twilio</div>
                <div><StatusLabel kind="pilot">Legacy pilot</StatusLabel></div>
                <div className="text-sm leading-6 text-slate-600">The existing Twilio WhatsApp integration remains available for the configured pilot account. Per-business Twilio credential onboarding is not part of the current self-service product.</div>
              </div>
            </div>
            <div className="mt-4 border-l-4 border-amber-500 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
              A Telegram bot is separate from a personal Telegram account. It only receives messages sent directly to that bot or in chats where it has been added with suitable permissions.
            </div>
          </section>

          <section id="workflow" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Operations" title="From message to delivered order" copy="PhoneERP keeps AI assistance behind explicit workflow boundaries so staff can correct uncertain information before fulfilment." />
            <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {[
                [Bot, "Received", "Intent and order details are extracted."],
                [ClipboardCheck, "Approved", "Owner reviews and confirms the draft."],
                [PackageCheck, "Packing", "Packer sees the approved item list."],
                [Truck, "Out for delivery", "Delivery staff receives the order details."],
                [CheckCircle2, "Delivered", "Customer receives status and bill information."],
              ].map(([Icon, title, copy]) => {
                const StepIcon = Icon as typeof Bot;
                return <article key={title as string} className="border border-slate-200 p-4"><StepIcon className="h-5 w-5 text-slate-600" /><h3 className="mt-4 text-sm font-bold">{title as string}</h3><p className="mt-2 text-xs leading-5 text-slate-500">{copy as string}</p></article>;
              })}
            </div>
          </section>

          <section id="customers" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Customer experience" title="Profiles, tracking, requests, and bills" copy="Customer identity is scoped to the business and channel. A customer using two connected businesses remains separate in each shop." />
            <ul className="mt-7 grid gap-3 text-sm leading-6 text-slate-700 sm:grid-cols-2">
              {["New customers are asked for missing profile details before an order is finalized.", "Text and voice notes use the same intent and extraction pipeline.", "Tracking questions are separated from new-order requests.", "Customers can view their order history through a private portal link.", "Pending orders can be corrected before owner approval where enabled.", "Delivery completion can send a public bill link through the originating channel."].map((item) => <li key={item} className="flex gap-3 border border-slate-200 p-4"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" /><span>{item}</span></li>)}
            </ul>
          </section>

          <section id="roles" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Access control" title="Give each person only the workspace they need" copy="Role separation protects owner functions while keeping packing and delivery screens focused on repeated operational work." />
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              {[[Users, "Owner", "Catalog, integrations, Action Cards, orders, requests, staff access, and reports."], [PackageCheck, "Packer", "Packing-stage orders and the transition to out for delivery."], [Truck, "Delivery", "Out-for-delivery orders and the final delivered transition."]].map(([Icon, title, copy]) => { const RoleIcon = Icon as typeof Users; return <article key={title as string} className="border border-slate-200 p-5"><RoleIcon className="h-5 w-5" /><h3 className="mt-4 font-bold">{title as string}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{copy as string}</p></article>; })}
            </div>
          </section>

          <section id="business-types" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Configuration" title="Current business support" copy="PhoneERP uses one shared pipeline with business-specific terminology and order requirements. Readiness is deliberately stated conservatively." />
            <div className="mt-8 space-y-3">
              <div className="flex flex-col gap-3 border border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-bold">Grocery and wholesale</h3><p className="mt-1 text-sm text-slate-600">Primary tested workflow for weighted items, packaged products, prices, addresses, and delivery times.</p></div><StatusLabel>Primary workflow</StatusLabel></div>
              <div className="flex flex-col gap-3 border border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-bold">Restaurant</h3><p className="mt-1 text-sm text-slate-600">Supports restaurant configuration and structured fields, but requires catalog and workflow testing with each pilot business before live use.</p></div><StatusLabel kind="pilot">In development</StatusLabel></div>
              <div className="flex flex-col gap-3 border border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-bold">Other business types</h3><p className="mt-1 text-sm text-slate-600">Configuration foundations exist, but production readiness requires real workflow validation and representative extraction tests.</p></div><StatusLabel kind="planned">Configuration stage</StatusLabel></div>
            </div>
          </section>

          <section id="security" className="scroll-mt-24 border-b border-slate-200 py-14">
            <SectionTitle eyebrow="Trust" title="Tenant isolation and credential handling" copy="Integration credentials and customer data must remain scoped to the owning business." />
            <div className="mt-8 border border-slate-200 bg-slate-50 p-5">
              <LockKeyhole className="h-5 w-5" />
              <ul className="mt-4 grid gap-2 text-sm leading-6 text-slate-700 sm:grid-cols-2">
                <li>Bot tokens are encrypted server-side and never returned to the browser.</li>
                <li>Every connected Telegram bot receives a unique webhook and verified secret.</li>
                <li>One bot cannot be active for two PhoneERP businesses.</li>
                <li>Customers, conversations, orders, and delivery messages are shop-scoped.</li>
                <li>Only owners can connect, check, or disconnect business integrations.</li>
                <li>Integration changes are recorded without logging plaintext credentials.</li>
              </ul>
            </div>
            <p className="mt-4 text-sm text-slate-600">For privacy, retention, and deletion details, read the <Link className="font-semibold text-slate-950 underline" href="/privacy">Privacy Policy</Link> and <Link className="font-semibold text-slate-950 underline" href="/data-deletion">Data Deletion guide</Link>.</p>
          </section>

          <section id="troubleshooting" className="scroll-mt-24 py-14">
            <SectionTitle eyebrow="Help" title="Common setup checks" copy="Use the connection health check before changing tokens or deleting integrations." />
            <div className="mt-8 divide-y divide-slate-200 border-y border-slate-200">
              {[
                ["Telegram says the token is invalid", "Create or rotate the token in BotFather, then paste the complete token without spaces. Never send it through chat or support screenshots."],
                ["The bot is connected but no orders appear", "Send a direct message to the connected bot, run Test connection, confirm the customer profile steps, and inspect whether the message was classified as an order."],
                ["An item has no price", "Add or correct the item in Catalog, including its selling unit and common aliases, then review the pending Action Card."],
                ["A staff member sees no orders", "Confirm the staff invite belongs to the same shop, the role is active, and the order has reached the stage assigned to that role."],
                ["WhatsApp onboarding is unavailable", "External business self-service onboarding is not generally released. Use an approved assisted pilot rather than creating unowned Meta assets for a customer."],
              ].map(([title, copy]) => <details key={title} className="group py-4"><summary className="cursor-pointer list-none font-semibold text-slate-900"><span className="flex items-center justify-between gap-4">{title}<Settings2 className="h-4 w-4 text-slate-400" /></span></summary><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{copy}</p></details>)}
            </div>
          </section>
        </main>
      </div>

      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>PhoneERP product documentation</span>
          <nav className="flex flex-wrap gap-4" aria-label="Documentation footer"><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/data-deletion">Data deletion</Link><Link href="/support">Support</Link></nav>
        </div>
      </footer>
    </div>
  );
}
