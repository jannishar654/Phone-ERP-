import {
  AudioLines,
  Check,
  ClipboardCheck,
  MessageSquareText,
  PackageCheck,
  ReceiptIndianRupee,
  Sparkles,
  Truck,
} from 'lucide-react';

const stages = [
  { label: 'Received', icon: MessageSquareText, active: true },
  { label: 'Reviewed', icon: ClipboardCheck, active: true },
  { label: 'Packing', icon: PackageCheck, active: true },
  { label: 'Delivery', icon: Truck, active: false },
  { label: 'Invoice', icon: ReceiptIndianRupee, active: false },
];

export default function OrderFlowVisual() {
  return (
    <div className="flow-visual" aria-label="PhoneERP order workflow preview">
      <div className="flow-visual-toolbar">
        <div className="flow-window-dots" aria-hidden="true"><span /><span /><span /></div>
        <span>Live order workflow</span>
        <span className="flow-live"><i /> Processing</span>
      </div>

      <div className="flow-visual-body">
        <div className="flow-message">
          <div className="flow-channel-icon"><AudioLines size={18} /></div>
          <div>
            <span>WhatsApp voice note</span>
            <p>“Kal 8 PM, do chicken biryani medium spicy aur ek paneer tikka...”</p>
          </div>
          <time>00:12</time>
        </div>

        <div className="flow-ai-line" aria-hidden="true"><span><Sparkles size={14} /> Intent + extraction</span></div>

        <div className="flow-order">
          <div className="flow-order-head">
            <div>
              <span>Action card</span>
              <h3>Order #PE-2048</h3>
            </div>
            <span className="flow-review-badge"><Check size={13} /> Ready to review</span>
          </div>
          <div className="flow-order-grid">
            <div><span>Customer</span><strong>Danish</strong></div>
            <div><span>Delivery</span><strong>Tomorrow, 8:00 PM</strong></div>
            <div className="flow-order-wide"><span>Items</span><strong>2 Chicken Biryani · 1 Paneer Tikka</strong></div>
            <div className="flow-order-wide"><span>Instructions</span><strong>Medium spicy · Less spicy</strong></div>
          </div>
        </div>

        <div className="flow-stages">
          {stages.map(({ label, icon: Icon, active }) => (
            <div key={label} className={active ? 'is-active' : ''}>
              <span><Icon size={15} /></span>
              <small>{label}</small>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
