# Meta WhatsApp Phase 2: Multi-Business Onboarding

Phase 2 lets multiple PhoneERP shops connect their own WhatsApp Business
accounts through one PhoneERP Meta app. It builds on the durable Phase 1
webhook pipeline; it must not create a second order-processing pipeline.

## Target experience

```text
Owner signs in to PhoneERP
-> Settings / Integrations / WhatsApp
-> Connect WhatsApp
-> Meta Embedded Signup
-> Owner selects or creates a Meta business, WABA, and phone number
-> PhoneERP validates and stores the connection
-> WABA is subscribed to the shared PhoneERP webhook
-> Connection becomes active
```

Every inbound webhook continues to use this trusted routing rule:

```text
Meta phone_number_id -> whatsapp_connections -> shop_id -> existing intent router
```

Never accept `shop_id`, WABA ID, phone-number ID, or token material from an
untrusted frontend request as proof of ownership.

## Prerequisites

Before public onboarding:

1. Phase 1 worker and monitoring are running without dead-letter growth.
2. PhoneERP Meta app is configured as a Tech Provider where required.
3. Business verification is complete.
4. App Review and Advanced Access are approved for the permissions required by
   the current Meta Embedded Signup documentation, including WhatsApp business
   management permissions.
5. Production privacy policy, terms, data deletion instructions, support email,
   and incident contact are published.
6. Billing ownership is decided: customer-paid directly to Meta or PhoneERP
   invoicing customers. Do not mix models silently.

## Backend additions

### Onboarding sessions

Create a short-lived `whatsapp_onboarding_sessions` table containing:

- random state nonce (store only a hash)
- authenticated owner user ID and shop ID
- expiration and one-time-consumed timestamp
- expected redirect URI
- status and safe error code

Only an authenticated owner may create a session. The callback must atomically
consume the state before exchanging Meta's authorization code.

### Connection lifecycle

Extend `whatsapp_connections` with the minimum onboarding metadata:

- Meta business ID
- WABA ID
- phone-number ID
- display number and verified name
- token reference, granted scopes, and token expiry if applicable
- connection status: pending, active, reconnect_required, disconnected, error
- connected/disconnected actor and timestamps

Keep the existing unique `(provider, phone_number_id)` constraint. Add an
appropriate uniqueness rule for active WABA/phone ownership after validating
Meta's current coexistence behavior.

Access tokens must live in a managed server-side secret store or encrypted
credential service. Supabase rows store only an opaque `token_reference`.

### API endpoints

Implement owner-only endpoints:

- `POST /integrations/whatsapp/onboarding-session`
- `POST /integrations/whatsapp/callback`
- `GET /integrations/whatsapp/status`
- `POST /integrations/whatsapp/health-check`
- `POST /integrations/whatsapp/reconnect`
- `DELETE /integrations/whatsapp/connection`

The callback must:

1. Validate and atomically consume the state nonce.
2. Exchange the authorization code on the backend.
3. Query Meta for the businesses/WABAs/phone numbers actually granted.
4. Verify the selected phone belongs to that authorization result.
5. Reject a phone number already mapped to another PhoneERP shop.
6. Store the credential reference and pending connection transactionally.
7. Subscribe the WABA to the PhoneERP app webhook.
8. Run a health check and only then mark the connection active.

If any step fails, leave a recoverable pending/error record and never partially
activate tenant routing.

## Frontend additions

Build `Settings -> Integrations -> WhatsApp` for owners only. It should show:

- Not connected / Connecting / Active / Reconnect required / Error
- display phone number and verified business name
- last successful webhook and health-check time
- Connect, Reconnect, Test connection, and Disconnect commands

The browser may receive Meta's short-lived signup result, but it must send only
the authorization result to the backend callback. It must never receive or
store a long-lived access token or Meta app secret.

## Templates and messaging rules

Add per-WABA template synchronization and store template name, language,
category, status, and last sync time. Use free-form replies only within Meta's
current customer-service window. Use approved templates for business-initiated
messages outside that window.

Start with utility templates for:

- order received
- order approved
- out for delivery
- delivered and invoice ready
- owner needs clarification

## Coexistence and number choices

Do not promise that every existing WhatsApp Business App number can be connected
unchanged. Eligibility and coexistence behavior depend on Meta's current rules,
region, account state, and onboarding flow. During signup:

- detect and explain eligibility before destructive number changes
- offer a dedicated business number as the safest pilot path
- clearly warn owners before migration or app-disconnection steps
- test inbound, outbound, templates, and the Business App after onboarding

## Rollout sequence

1. Internal second shop with a separate test WABA/number.
2. One supervised pilot business with manual onboarding support.
3. Five-business pilot with connection health and dead-letter alerts.
4. Complete App Review/Advanced Access and operational support readiness.
5. Enable self-service Embedded Signup gradually behind a feature flag.

Release gates for each pilot business:

- tenant routing test proves no cross-shop access
- duplicate webhook creates one Action Card
- text and voice orders work
- status callbacks update the correct outbound message
- token rotation/reconnect works
- disconnect stops routing immediately
- failed worker events are visible and recoverable
- templates and billing responsibility are confirmed

## Team boundary

Nasir/Jannishar can build business onboarding, catalog setup, and configurable
business workflows against `shop_id`. The Meta integration owns connection
authorization, WABA subscription, credentials, and phone-number routing. Both
areas meet only at the existing shop record and `whatsapp_connections`; neither
team should fork or replace the intent router and Action Card pipeline.

