# Meta WhatsApp Phase 1 Production Runbook

This phase hardens the existing PhoneERP Meta Cloud API pilot. It does not
enable public multi-business Embedded Signup.

## Processing contract

1. Render verifies `X-Hub-Signature-256` against `META_APP_SECRET`.
2. Each message/status event is inserted into `whatsapp_webhook_events`.
3. Only after persistence succeeds does the webhook return HTTP 200.
4. The web service attempts immediate processing for low latency.
5. A separate worker claims pending/retry events atomically and recovers work
   after a crash or Render restart.
6. `phone_number_id` is resolved through an active `whatsapp_connections` row.
7. Outbound Meta message IDs and delivery/read/failure states are recorded in
   `whatsapp_outbound_messages`.

## Deployment order

1. Apply `backend/sql/023_meta_whatsapp_phase_one_hardening.sql` in Supabase.
2. Verify the existing pilot row in `whatsapp_connections` is active and has
   the correct `phone_number_id` and `shop_id`.
3. Set `token_reference` to `env:META_WHATSAPP_ACCESS_TOKEN` for the pilot.
4. Deploy the backend web service.
5. Create a Render Background Worker from the same repository and backend root.
6. Give the worker the same server-only environment variables as the backend.
7. Send one inbound text, one voice note, and confirm delivery/read status.

Because Meta only permits free-form business replies inside the rolling
customer-service window, Phase 1 records `customer_channels.last_inbound_at`.
Delivery/bill text is skipped outside 24 hours until an approved utility
template is configured in Phase 2.

Pilot connection update:

```sql
UPDATE public.whatsapp_connections
SET token_reference = 'env:META_WHATSAPP_ACCESS_TOKEN',
    status = 'active',
    connected_at = COALESCE(connected_at, NOW())
WHERE provider = 'meta_cloud'
  AND phone_number_id = '<PILOT_PHONE_NUMBER_ID>';
```

## Render services

Web service command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Background Worker command:

```text
python -m app.workers.meta_whatsapp_worker
```

Use `backend` as the root directory for both services. The worker must use the
Supabase service-role key because the inbox and status tables are service-only.

Required Render variables:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
META_WHATSAPP_ACCESS_TOKEN
META_WHATSAPP_PHONE_NUMBER_ID
META_WHATSAPP_WABA_ID
META_WHATSAPP_VERIFY_TOKEN
META_APP_SECRET
META_GRAPH_API_VERSION
META_WHATSAPP_ALLOW_DEFAULT_CONNECTION_FALLBACK=false
META_WHATSAPP_MAX_WEBHOOK_BYTES=1048576
META_WHATSAPP_MAX_MEDIA_BYTES=15728640
META_WHATSAPP_WORKER_BATCH_SIZE=10
META_WHATSAPP_WORKER_POLL_SECONDS=2
META_WHATSAPP_RETRY_BASE_SECONDS=30
```

Never add these variables to Vercel or prefix them with `NEXT_PUBLIC_`.

## Production checks

Inbox health:

```sql
SELECT processing_status, COUNT(*)
FROM public.whatsapp_webhook_events
GROUP BY processing_status
ORDER BY processing_status;
```

Dead-letter events:

```sql
SELECT id, phone_number_id, event_kind, attempts, last_error, created_at
FROM public.whatsapp_webhook_events
WHERE processing_status IN ('dead_letter', 'unroutable')
ORDER BY created_at DESC
LIMIT 50;
```

Connection health:

```sql
SELECT shop_id, phone_number_id, status, last_webhook_at,
       last_health_check_at, failure_count, last_error
FROM public.whatsapp_connections
WHERE provider = 'meta_cloud'
ORDER BY updated_at DESC;
```

The worker removes webhook payloads after `retention_expires_at` (30 days by
default). Review this retention period against the pilot privacy policy before
public onboarding.

## Safe rollback

The migration is additive. Rolling back application code does not remove or
change orders, customers, or existing connection mappings. Keep the new tables
for audit/recovery rather than dropping them during an incident.
