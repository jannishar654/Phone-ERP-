# Action Card API Contract v2

## Overview
The Action Card API provides structured grocery order entities from unstructured text and audio transcripts. This update (v2) introduces an **Ordered Operation Log**, ensuring predictable reduction of sequences like additions, cancellations, updates, returns, substitutions, and references.

## JSON Contract

### `POST /extract-action-card`
Extracts entities from a transcript using the specified pipeline.

**Request Payload:**
```json
{
  "transcript": "string",
  "source": "audio|text",
  "stt_provider": "gemini|sarvam",
  "extraction_provider": "gemini|ollama",
  "pipeline": "gemini_gemini|sarvam_gemini|sarvam_ollama"
}
```

**Response Payload (`ActionCard`):**
```json
{
  "id": "uuid",
  "customer_name": "string",
  "customer_phone": "string",
  "items": [
    {
      "name": "string",
      "quantity": "number | null",
      "unit": "string",
      "price": "number | null"
    }
  ],
  "delivery_address": "string",
  "delivery_time": "string",
  "delivery_time_raw": "string",
  "delivery_time_normalized": "string | null",
  "delivery_time_confidence": "number",
  "delivery_time_warning": "string | null",
  "risk_flags": ["string"],
  "missing_fields": ["string"],
  "validation_warnings": ["string"],
  "payment_method": "string",
  "status": "pending",
  "source": "audio|text",
  "message_type": "ORDER",
  "confidence": "number",
  "stt_provider": "string",
  "extraction_provider": "string",
  "metadata": {
    "pipeline": "string",
    "extraction_notes": "string",
    "transcript_original": "string",
    "transcript_normalized": "string",
    "operations": [
      {
        "sequence": 1,
        "operation_id": "string",
        "target_operation_id": "string",
        "type": "ADD|SET_QUANTITY|CANCEL|RETURN|SUBSTITUTE|PREVIOUS_ORDER_REFERENCE",
        "raw_product": "string",
        "quantity_raw": "string",
        "quantity": 1,
        "unit": "string",
        "condition": "string",
        "evidence": "string"
      }
    ],
    "cancelled_items": [],
    "return_items": [],
    "substitution_instructions": [],
    "previous_order_reference": "string | null",
    "invalid_operations": [],
    "operation_warnings": []
  },
  "transcript": "string",
  "created_at": "timestamp"
}
```

## Operation Definitions

- **ADD**: Adds a new item to the active cart.
- **SET_QUANTITY**: Modifies the quantity of an existing item. Requires matching by `target_operation_id` or exact `raw_product`.
- **CANCEL**: Removes an existing item from the active cart and moves it to `metadata.cancelled_items`.
- **RETURN**: Logs an item to be returned in `metadata.return_items` without adding it to the active order.
- **SUBSTITUTE**: Logs substitution instructions in `metadata.substitution_instructions` without inventing new active items.
- **PREVIOUS_ORDER_REFERENCE**: Flags previous order constraints (e.g. "pichli baar wala order") requiring manual review.

## Audio Storage & Consent

Voice recordings are **not** automatically uploaded during entity extraction. They require an explicit user action ("Save Audio for AI Eval") governed by user consent.

Audio Metadata Table (`voice_recordings`):
- `id`: uuid
- `user_id`: auth.uid()
- `action_card_id`: references `action_cards(id)`
- `storage_path`: User-private path (`user_id/uuid.ext`)
- `mime_type`: string
- `duration_seconds`: integer
- `consent_for_evaluation`: boolean
- `pipeline`: string
- `transcript`: text

If metadata insert fails, the corresponding object is immediately removed from storage. Service role credentials are never exposed to the frontend.

## UI Behavior
- Extraction failures or missing information flag the card with warnings but do not crash the UI.
- Unparseable/ambiguous operations are preserved in `metadata.operation_warnings` and trigger UI review indicators.
- Backward compatibility is maintained for cards created without the `operations` array.
