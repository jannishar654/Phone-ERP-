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

## Implemented foundation

PhoneERP now includes:

- owner-only onboarding, callback, status, health-check, and disconnect APIs
- one-time, hashed signup state with atomic consumption
- server-side Meta code exchange and granted-asset verification
- one phone-number-to-one-shop enforcement
- AES-256-GCM encrypted per-business credentials in a service-role-only table
- WABA webhook subscription and activation only after a Graph API health check
- Cloud API phone registration with a one-time six-digit PIN that is not stored
- an owner settings page using Meta's JavaScript SDK
- reconnect state, safe audit logs, and a per-shop pilot allowlist

The feature defaults to off. Existing production connections continue to use
their current environment-token references and webhook pipeline.

## Backend design

### Onboarding sessions

The short-lived `whatsapp_onboarding_sessions` table contains:

- random state nonce (store only a hash)
- authenticated owner user ID and shop ID
- expiration and one-time-consumed timestamp
- expected redirect URI
- status and safe error code

Only an authenticated owner may create a session. The callback must atomically
consume the state before exchanging Meta's authorization code.

### Connection lifecycle

`whatsapp_connections` contains the minimum onboarding metadata:

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

Access tokens are encrypted using AES-256-GCM. The owner-readable connection
row stores only an opaque `db:<connection-id>` reference; encrypted values live
in a separate service-role-only table. The master key exists only in Render.

### API endpoints

Implemented owner-only endpoints:

- `POST /integrations/whatsapp/onboarding-session`
- `POST /integrations/whatsapp/callback`
- `GET /integrations/whatsapp/status`
- `POST /integrations/whatsapp/health-check`
- `DELETE /integrations/whatsapp/connection`

Reconnect starts a fresh onboarding session through the same Connect action.

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

## Frontend

`Settings -> Integrations -> WhatsApp` is owner-only and shows:

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

Use both rollout controls in Render:

```text
META_WHATSAPP_EMBEDDED_SIGNUP_ENABLED=true
META_WHATSAPP_EMBEDDED_SIGNUP_ALLOWED_SHOP_IDS=<pilot-shop-uuid>
```

Add comma-separated shop UUIDs as pilots are approved. An empty allowlist means
no business can start signup. Use `*` only after public Meta approval and
operational readiness.

## Deployment runbook

1. In Meta Developer Dashboard, configure WhatsApp Embedded Signup and record
   its configuration ID. Keep the PhoneERP callback domain and privacy/data
   deletion URLs current.
2. Apply `022_meta_whatsapp_cloud_api.sql` and
   `023_meta_whatsapp_phase_one_hardening.sql` if they are not already present,
   then apply `025_meta_whatsapp_embedded_signup.sql` in Supabase.
3. Generate a 32-byte encryption key locally and store it only in Render:

   ```bash
   python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

4. Set the new Render variables from `backend/.env.example`, initially with the
   feature disabled. Do not put the app secret or encryption key in Vercel.
5. Deploy the backend and frontend. Verify the existing production number still
   receives and replies to a grocery order.
6. Add only the internal test shop UUID to the allowlist, enable the feature,
   and redeploy Render.
7. Sign in as that shop owner, open the WhatsApp integration page, and complete
   Meta signup with a separate test WABA/number. Enter the existing two-step
   PIN for an already configured number, or choose a new PIN for a new number.
8. Run Test connection, then verify inbound text, Hinglish order, voice note,
   duplicate delivery, status callbacks, customer portal, and disconnect.
9. Check that the same phone cannot be connected to a second PhoneERP shop and
   that a non-allowlisted shop cannot start signup.

No new secret is required in Vercel. Vercel continues to use only the public
backend URL and existing Supabase public values.

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
