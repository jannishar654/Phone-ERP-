import { ImageResponse } from 'next/og';

export const alt = 'PhoneERP turns conversational orders into structured business operations';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

const workflow = ['Received', 'Reviewed', 'Packing', 'Delivery'];

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          position: 'relative',
          overflow: 'hidden',
          background: '#08090a',
          color: '#f5f5f2',
          fontFamily: 'Arial, sans-serif',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            opacity: 0.22,
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.12) 1px, transparent 1px)',
            backgroundSize: '64px 64px',
          }}
        />

        <div
          style={{
            position: 'relative',
            width: '100%',
            display: 'flex',
            alignItems: 'stretch',
            justifyContent: 'space-between',
            padding: '64px 68px',
          }}
        >
          <div style={{ width: 610, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
              <div
                style={{
                  width: 68,
                  height: 68,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #4b4e52',
                  borderRadius: 14,
                  background: '#15171a',
                  fontSize: 22,
                  fontWeight: 700,
                }}
              >
                <span style={{ paddingRight: 9 }}>P</span>
                <span style={{ width: 1, height: 35, background: '#c8a96b' }} />
                <span style={{ paddingLeft: 9 }}>E</span>
              </div>
              <div style={{ display: 'flex', fontSize: 36, fontWeight: 700 }}>
                Phone<span style={{ color: '#c8a96b' }}>ERP</span>
              </div>
            </div>

            <div
              style={{
                marginTop: 72,
                display: 'flex',
                flexDirection: 'column',
                fontSize: 54,
                fontWeight: 600,
                lineHeight: 1.08,
                letterSpacing: '-1px',
              }}
            >
              <span>Conversations in.</span>
              <span>Operations out.</span>
            </div>

            <div
              style={{
                marginTop: 28,
                width: 570,
                display: 'flex',
                color: '#b3b6ba',
                fontSize: 24,
                lineHeight: 1.45,
              }}
            >
              Turn customer text and voice messages into reviewable orders, fulfilment, tracking and invoices.
            </div>

            <div style={{ marginTop: 'auto', display: 'flex', gap: 12 }}>
              {['Text orders', 'Voice notes', 'Human review'].map((label) => (
                <span
                  key={label}
                  style={{
                    display: 'flex',
                    border: '1px solid #383b3f',
                    borderRadius: 999,
                    padding: '10px 16px',
                    color: '#d4d5d2',
                    background: '#111316',
                    fontSize: 17,
                  }}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>

          <div
            style={{
              width: 380,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #36393d',
              borderRadius: 18,
              background: '#111316',
              padding: '28px 28px 26px',
              boxShadow: '0 28px 70px rgba(0,0,0,0.4)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#777c82', fontSize: 16, textTransform: 'uppercase', letterSpacing: 2 }}>
                Live workflow
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#d5c08f', fontSize: 15 }}>
                <span style={{ width: 9, height: 9, borderRadius: 99, background: '#c8a96b' }} />
                Active
              </span>
            </div>

            <div
              style={{
                marginTop: 30,
                display: 'flex',
                flexDirection: 'column',
                border: '1px solid #2c2f33',
                borderRadius: 13,
                background: '#17191c',
                padding: 22,
              }}
            >
              <span style={{ color: '#777c82', fontSize: 14, textTransform: 'uppercase' }}>Customer message</span>
              <span style={{ marginTop: 12, color: '#e4e4df', fontSize: 21, lineHeight: 1.4 }}>
                “Kal 8 PM, 2 biryani bhej dena.”
              </span>
            </div>

            <div style={{ margin: '22px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ width: 34, height: 1, background: '#5e5239' }} />
              <span style={{ color: '#c8a96b', fontSize: 15 }}>AI extraction + owner review</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {workflow.map((stage, index) => (
                <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <span
                    style={{
                      width: 30,
                      height: 30,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '1px solid #665a40',
                      borderRadius: 99,
                      color: '#c8a96b',
                      fontSize: 14,
                    }}
                  >
                    {index + 1}
                  </span>
                  <span style={{ color: index < 2 ? '#f5f5f2' : '#8d9196', fontSize: 19 }}>{stage}</span>
                </div>
              ))}
            </div>

            <div
              style={{
                marginTop: 'auto',
                display: 'flex',
                borderTop: '1px solid #2c2f33',
                paddingTop: 20,
                color: '#92969b',
                fontSize: 15,
              }}
            >
              <span>Built for practical business workflows in India</span>
            </div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
