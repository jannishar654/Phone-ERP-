import asyncio
import datetime
import hashlib
import logging
import re
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from app.controllers.action_card import ActionCardController
from app.schemas.inbound import (
    ConversationIntent,
    IntentClassification,
    NormalizedInboundMessage,
)
from app.services.gemini import GeminiService
from app.services.supabase import supabase_client


logger = logging.getLogger(__name__)

TERMINAL_INBOUND_STATUSES = {"processed", "needs_review", "failed", "skipped"}
MAX_PROVIDER_RETRIES = 3
CLASSIFICATION_TIMEOUT_SECONDS = 5
EXTRACTION_TIMEOUT_SECONDS = 8


class IntentRouter:
    @staticmethod
    def classify_intent_deterministically(
        text: str,
    ) -> Optional[IntentClassification]:
        """Resolve strong English, Hindi, and Hinglish signals without an AI call."""
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized:
            return IntentClassification(
                intent=ConversationIntent.UNCERTAIN, confidence=0.0
            )

        if re.fullmatch(
            r"(?:hi|hello|hey|namaste|namaskar|thanks|thank you|dhanyavaad|"
            r"shukriya|नमस्ते|नमस्कार|धन्यवाद)[!. ]*",
            normalized,
        ):
            return IntentClassification(
                intent=ConversationIntent.GENERAL_MESSAGE, confidence=0.99
            )

        price_patterns = (
            r"\b(?:price|rate|cost|kitna|kitne|bhaav|bhav)\b",
            r"(?:कीमत|दाम|रेट|भाव|कितना|कितने)",
            r"how much",
        )
        if any(re.search(pattern, normalized) for pattern in price_patterns):
            return IntentClassification(
                intent=ConversationIntent.PRICE_ENQUIRY, confidence=0.98
            )

        tracking_patterns = (
            r"\b(?:track|tracking|status|dispatched|arrive|delivery status)\b",
            r"\bwhere\b.*\b(?:order|delivery)\b",
            r"\bwhen\b.*\b(?:arrive|delivered|delivery)\b",
            r"\b(?:order|delivery)\s+(?:kaha|kahaan|kidhar)\b",
            r"(?:ऑर्डर|डिलीवरी).*(?:कहाँ|स्थिति|स्टेटस)",
        )
        if any(re.search(pattern, normalized) for pattern in tracking_patterns):
            return IntentClassification(
                intent=ConversationIntent.ORDER_TRACKING, confidence=0.97
            )

        cancel_patterns = (
            r"\b(?:cancel|cancelled|cancellation|nahi bhejna|mat bhejna)\b",
            r"(?:कैंसिल|रद्द|मत भेजना|नहीं भेजना)",
        )
        if any(re.search(pattern, normalized) for pattern in cancel_patterns):
            return IntentClassification(
                intent=ConversationIntent.ORDER_CANCEL, confidence=0.98
            )

        update_patterns = (
            r"\b(?:change|modify|update|replace|remove|add)\b.*\b(?:order|mera|my)\b",
            r"\b(?:order|mera|my)\b.*\b(?:change|modify|update|replace|remove|add)\b",
            r"(?:ऑर्डर).*(?:बदल|जोड़|हटा|अपडेट)",
        )
        if any(re.search(pattern, normalized) for pattern in update_patterns):
            return IntentClassification(
                intent=ConversationIntent.ORDER_UPDATE, confidence=0.96
            )

        payment_patterns = (
            r"\b(?:payment|pay|paid|balance|due|dues|credit|udhaar|udhar|invoice)\b",
            r"(?:पेमेंट|भुगतान|बकाया|उधार|बिल)",
        )
        if any(re.search(pattern, normalized) for pattern in payment_patterns):
            return IntentClassification(
                intent=ConversationIntent.PAYMENT_QUERY, confidence=0.94
            )

        support_patterns = (
            r"\b(?:complaint|problem|issue|damaged|bad quality|call me|human support|"
            r"need help|help me|opening time|closing time|shop open)\b",
            r"(?:शिकायत|समस्या|खराब|कॉल करो|दुकान खुली)",
        )
        if any(re.search(pattern, normalized) for pattern in support_patterns):
            return IntentClassification(
                intent=ConversationIntent.BUSINESS_SUPPORT, confidence=0.94
            )

        quantity_with_unit = re.search(
            r"(?:\b\d+(?:\.\d+)?|\b(?:ek|teen|char|chaar|paanch|chhe|saat|aath|"
            r"nau|das|bees|pachas|sau|aadha|adhaa|dedh|dhai)\b|"
            r"(?:एक|दो|तीन|चार|पांच|छह|सात|आठ|नौ|दस|बीस|पचास|सौ|आधा|डेढ़|ढाई))"
            r"\s*(?:kg|kgs|kilo|kilogram|g|gram|grams|litre|liter|litres|liters|l|"
            r"ml|packet|packets|pack|packs|piece|pieces|pcs|box|boxes|bottle|bottles|"
            r"किलो|किलोग्राम|ग्राम|लीटर|मिलीलीटर|पैकेट|पीस|डिब्बा|बोतल)"
            r"(?=\s|$|[,.!?।])",
            normalized,
        )
        purchase_patterns = (
            r"\b(?:send|deliver|order|book|buy|purchase|need|want)\b",
            r"\b(?:bhej|bhejna|bhejdo|bhej do|bhej dena|chahiye|de do|dedo|"
            r"dena|dijiye|de dena|laga do|pahuncha|pahucha)\b",
            r"(?:भेज|चाहिए|देना|दे दो|दीजिए|पहुंचा|ऑर्डर|खरीद)",
        )
        has_purchase_intent = any(
            re.search(pattern, normalized) for pattern in purchase_patterns
        )
        has_product_after_quantity = bool(
            quantity_with_unit
            and re.match(
                r"\s*[\w\u0900-\u097F][\w\u0900-\u097F+&()./'-]*",
                normalized[quantity_with_unit.end() :],
            )
        )
        if quantity_with_unit and (
            has_purchase_intent or has_product_after_quantity
        ):
            return IntentClassification(
                intent=ConversationIntent.NEW_ORDER, confidence=0.97
            )
        if has_purchase_intent:
            return IntentClassification(
                intent=ConversationIntent.NEW_ORDER, confidence=0.72
            )

        promotion_patterns = (
            r"\b(?:earn money|limited offer|click here|promo code|investment scheme)\b",
            r"(?:कमाई करें|ऑफर पाने के लिए क्लिक)",
        )
        if any(re.search(pattern, normalized) for pattern in promotion_patterns):
            return IntentClassification(
                intent=ConversationIntent.SPAM, confidence=0.96
            )

        return None

    @staticmethod
    async def process_inbound_message(msg: NormalizedInboundMessage) -> Dict[str, Any]:
        if not supabase_client:
            logger.error("Intent router unavailable: database client is not configured")
            return {
                "status": "error",
                "reply_message": "System error. Please try again shortly.",
            }

        inbound_id, registration_status = IntentRouter._register_inbound_message(msg)
        if registration_status == "duplicate":
            return {"status": "skipped", "reply_message": None}
        if not inbound_id:
            return {
                "status": "error",
                "reply_message": "System error. Please try again shortly.",
            }

        conversation = IntentRouter._get_or_create_conversation(
            msg.shop_id, msg.customer_id, msg.channel.value
        )
        if not conversation:
            IntentRouter._update_inbound_status(
                inbound_id, "failed", last_error="ConversationUnavailable"
            )
            return {
                "status": "error",
                "reply_message": "System error. Please try again shortly.",
            }

        state = conversation.get("state", "idle")
        if state == "awaiting_confirmation" and IntentRouter._is_expired(
            conversation.get("expires_at")
        ):
            expired_claimed = IntentRouter._conditional_conversation_update(
                conversation["id"],
                expected_state="awaiting_confirmation",
                updates={
                    "state": "idle",
                    "pending_intent": None,
                    "draft_payload": None,
                    "expires_at": None,
                },
            )
            IntentRouter._update_inbound_status(
                inbound_id, "processed" if expired_claimed else "skipped"
            )
            return {
                "status": "processed" if expired_claimed else "skipped",
                "reply_message": (
                    "Draft expired. Please send your order again."
                    if expired_claimed
                    else "This order draft was already handled."
                ),
            }

        IntentRouter._update_conversation(
            conversation["id"], {"last_message_at": IntentRouter._utc_now()}
        )

        if state == "awaiting_confirmation":
            return await IntentRouter._handle_confirmation(
                conversation, msg.raw_text, inbound_id
            )

        IntentRouter._update_inbound_status(inbound_id, "classifying")
        context = IntentRouter._get_business_context(msg.shop_id, msg.metadata)
        classification = IntentRouter.classify_intent_deterministically(msg.raw_text)
        classifier_warning = None
        try:
            if classification is None:
                raw_classification = await asyncio.wait_for(
                    GeminiService.classify_intent(
                        msg.raw_text, business_context=context
                    ),
                    timeout=CLASSIFICATION_TIMEOUT_SECONDS,
                )
                classification = IntentClassification.model_validate(
                    raw_classification
                )
                if not classification.available:
                    logger.warning(
                        "AI intent classifier unavailable for inbound_id=%s; "
                        "using safe uncertain fallback",
                        inbound_id,
                    )
                    classification = IntentClassification(
                        intent=ConversationIntent.UNCERTAIN,
                        confidence=0.0,
                    )
                    classifier_warning = "IntentClassifierUnavailable"
        except (ValidationError, TypeError, ValueError) as exc:
            logger.warning(
                "Intent classifier returned invalid output for inbound_id=%s (%s)",
                inbound_id,
                type(exc).__name__,
            )
            IntentRouter._update_inbound_status(
                inbound_id, "needs_review", last_error="InvalidClassifierOutput"
            )
            return {
                "status": "needs_review",
                "reply_message": (
                    "I could not confidently understand that message. "
                    "Please contact the business directly."
                ),
            }
        except Exception as exc:
            logger.warning(
                "Intent classification unavailable for inbound_id=%s (%s); "
                "using safe uncertain fallback",
                inbound_id,
                type(exc).__name__,
            )
            classification = IntentClassification(
                intent=ConversationIntent.UNCERTAIN,
                confidence=0.0,
            )
            classifier_warning = type(exc).__name__

        intent = classification.intent.value
        confidence = classification.confidence
        IntentRouter._update_inbound_status(
            inbound_id,
            "classified",
            detected_intent=intent,
            confidence=confidence,
            last_error=classifier_warning,
        )

        if classification.intent == ConversationIntent.NEW_ORDER:
            if confidence >= 0.85:
                return await IntentRouter._process_high_confidence_order(
                    msg, conversation, inbound_id
                )
            if confidence >= 0.60:
                return await IntentRouter._process_medium_confidence_order(
                    msg, conversation, inbound_id
                )

        return IntentRouter._handle_other_intent(
            classification.intent, conversation, inbound_id
        )

    @staticmethod
    def _handle_other_intent(
        intent: ConversationIntent,
        conversation: Dict[str, Any],
        inbound_id: str,
    ) -> Dict[str, Any]:
        IntentRouter._update_conversation(
            conversation["id"],
            {"state": "idle", "pending_intent": None, "expires_at": None},
        )

        if intent == ConversationIntent.SPAM:
            IntentRouter._update_inbound_status(inbound_id, "skipped")
            return {"status": "skipped", "reply_message": None}

        if intent == ConversationIntent.GENERAL_MESSAGE:
            IntentRouter._update_inbound_status(inbound_id, "processed")
            return {
                "status": "processed",
                "reply_message": (
                    "Would you like to place an order, track an order, "
                    "or contact the business?"
                ),
            }

        if intent == ConversationIntent.ORDER_TRACKING:
            IntentRouter._update_inbound_status(inbound_id, "processed")
            return {
                "status": "processed",
                "reply_message": "Use /orders to check your recent order status.",
            }

        review_messages = {
            ConversationIntent.ORDER_UPDATE: (
                "Order changes need shopkeeper approval. Please contact the business directly."
            ),
            ConversationIntent.ORDER_CANCEL: (
                "Cancellations need shopkeeper approval. Please contact the business directly."
            ),
            ConversationIntent.PRICE_ENQUIRY: (
                "I cannot confirm that price automatically. Please contact the business directly."
            ),
            ConversationIntent.PAYMENT_QUERY: (
                "Payment questions need staff assistance. Please contact the business directly."
            ),
            ConversationIntent.BUSINESS_SUPPORT: (
                "Please contact the business directly for assistance."
            ),
            ConversationIntent.UNCERTAIN: (
                "I could not confidently identify your request. "
                "Please contact the business directly."
            ),
            ConversationIntent.NEW_ORDER: (
                "I could not confidently confirm this as an order. "
                "Please resend it with clear items and quantities."
            ),
        }
        IntentRouter._update_conversation(
            conversation["id"],
            {"state": "human_support", "pending_intent": intent.value},
        )
        IntentRouter._update_inbound_status(inbound_id, "needs_review")
        return {
            "status": "needs_review",
            "reply_message": review_messages[intent],
        }

    @staticmethod
    async def _handle_confirmation(
        conversation: Dict[str, Any], text: str, inbound_id: str
    ) -> Dict[str, Any]:
        text_lower = text.strip().lower()
        words = set(re.findall(r"\b\w+\b", text_lower))
        yes_words = {
            "yes",
            "y",
            "ha",
            "haan",
            "han",
            "ok",
            "theek",
            "thik",
            "done",
            "confirm",
        }
        no_words = {"no", "n", "nahi", "na", "cancel", "wrong", "galat"}
        is_yes = bool(words & yes_words) and not bool(words & no_words)
        is_no = bool(words & no_words)

        if not is_yes and not is_no:
            IntentRouter._update_inbound_status(inbound_id, "processed")
            return {
                "status": "processed",
                "reply_message": "Please reply 'yes' to confirm, or 'no' to cancel.",
            }

        if is_no:
            claimed = IntentRouter._conditional_conversation_update(
                conversation["id"],
                expected_state="awaiting_confirmation",
                updates={
                    "state": "idle",
                    "pending_intent": None,
                    "draft_payload": None,
                    "expires_at": None,
                },
            )
            IntentRouter._update_inbound_status(
                inbound_id, "processed" if claimed else "skipped"
            )
            return {
                "status": "processed" if claimed else "skipped",
                "reply_message": (
                    "Draft cancelled. You can send a new order."
                    if claimed
                    else "This order draft was already handled."
                ),
            }

        claimed = IntentRouter._conditional_conversation_update(
            conversation["id"],
            expected_state="awaiting_confirmation",
            updates={"state": "creating_order"},
        )
        if not claimed:
            IntentRouter._update_inbound_status(inbound_id, "skipped")
            return {
                "status": "skipped",
                "reply_message": "This order confirmation is already being processed.",
            }

        draft = conversation.get("draft_payload")
        if not draft:
            IntentRouter._update_conversation(
                conversation["id"],
                {"state": "idle", "draft_payload": None, "expires_at": None},
            )
            IntentRouter._update_inbound_status(inbound_id, "processed")
            return {
                "status": "processed",
                "reply_message": "Draft expired. Please send your order again.",
            }

        try:
            owner_id = IntentRouter._require_owner_id(conversation["shop_id"])
            card = ActionCardController.create_card(draft, user_id=owner_id)
            if not card:
                raise RuntimeError("Action card creation returned no result")
            IntentRouter._update_conversation(
                conversation["id"],
                {
                    "state": "order_created",
                    "pending_intent": None,
                    "draft_payload": None,
                    "expires_at": None,
                },
            )
            IntentRouter._update_inbound_status(inbound_id, "processed")
            return {
                "status": "processed",
                "reply_message": "Order confirmed. Shopkeeper will review it.",
            }
        except Exception as exc:
            logger.error(
                "Confirmed order creation failed for inbound_id=%s (%s)",
                inbound_id,
                type(exc).__name__,
            )
            IntentRouter._conditional_conversation_update(
                conversation["id"],
                expected_state="creating_order",
                updates={"state": "awaiting_confirmation"},
            )
            IntentRouter._update_inbound_status(
                inbound_id, "failed", last_error=type(exc).__name__
            )
            return {
                "status": "error",
                "reply_message": "Order creation failed. Please reply 'yes' to retry.",
            }

    @staticmethod
    async def _process_high_confidence_order(
        msg: NormalizedInboundMessage,
        conversation: Dict[str, Any],
        inbound_id: str,
    ) -> Dict[str, Any]:
        IntentRouter._update_inbound_status(inbound_id, "extracting")
        try:
            extracted = await asyncio.wait_for(
                GeminiService.extract_order_details(msg.raw_text),
                timeout=EXTRACTION_TIMEOUT_SECONDS,
            )
            card_data = IntentRouter._build_card_data(extracted, msg, inbound_id)
            owner_id = IntentRouter._require_owner_id(msg.shop_id)
            card = ActionCardController.create_card(card_data, user_id=owner_id)
            if not card:
                raise RuntimeError("Action card creation returned no result")
            IntentRouter._update_conversation(
                conversation["id"],
                {
                    "state": "order_created",
                    "pending_intent": None,
                    "draft_payload": None,
                    "expires_at": None,
                },
            )
            IntentRouter._update_inbound_status(inbound_id, "processed")
            return {
                "status": "processed",
                "reply_message": "Order received. Shopkeeper will review it.",
            }
        except ValueError as exc:
            IntentRouter._update_inbound_status(
                inbound_id, "needs_review", last_error=type(exc).__name__
            )
            return {
                "status": "needs_review",
                "reply_message": (
                    "I could not validate the products and quantities. "
                    "Please resend the order with clear items and quantities."
                ),
            }
        except Exception as exc:
            logger.error(
                "Order extraction failed for inbound_id=%s (%s)",
                inbound_id,
                type(exc).__name__,
            )
            IntentRouter._update_inbound_status(
                inbound_id, "failed", last_error=type(exc).__name__
            )
            return {
                "status": "error",
                "reply_message": "Order processing failed. Please try again.",
            }

    @staticmethod
    async def _process_medium_confidence_order(
        msg: NormalizedInboundMessage,
        conversation: Dict[str, Any],
        inbound_id: str,
    ) -> Dict[str, Any]:
        IntentRouter._update_inbound_status(inbound_id, "extracting")
        try:
            extracted = await asyncio.wait_for(
                GeminiService.extract_order_details(msg.raw_text),
                timeout=EXTRACTION_TIMEOUT_SECONDS,
            )
            card_data = IntentRouter._build_card_data(extracted, msg, inbound_id)
            expires_at = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(minutes=30)
            ).isoformat()
            updated = IntentRouter._update_conversation(
                conversation["id"],
                {
                    "state": "awaiting_confirmation",
                    "pending_intent": ConversationIntent.NEW_ORDER.value,
                    "draft_payload": card_data,
                    "expires_at": expires_at,
                },
            )
            if not updated:
                raise RuntimeError("Failed to save order confirmation draft")
            IntentRouter._update_inbound_status(
                inbound_id, "awaiting_confirmation"
            )
            item_list = ", ".join(
                f"{item['quantity']} {item.get('unit') or ''} {item['name']}".strip()
                for item in card_data["items"]
            )
            return {
                "status": "awaiting_confirmation",
                "reply_message": (
                    f"I understood: {item_list}. "
                    "Reply 'yes' to confirm or 'no' to cancel."
                ),
            }
        except ValueError as exc:
            IntentRouter._update_inbound_status(
                inbound_id, "needs_review", last_error=type(exc).__name__
            )
            return {
                "status": "needs_review",
                "reply_message": (
                    "I could not validate the products and quantities. "
                    "Please send the order again with clear quantities."
                ),
            }
        except Exception as exc:
            logger.error(
                "Order draft creation failed for inbound_id=%s (%s)",
                inbound_id,
                type(exc).__name__,
            )
            IntentRouter._update_inbound_status(
                inbound_id, "failed", last_error=type(exc).__name__
            )
            return {
                "status": "error",
                "reply_message": "Order processing failed. Please try again.",
            }

    @staticmethod
    def _build_card_data(
        extracted: Dict[str, Any],
        msg: NormalizedInboundMessage,
        inbound_id: str,
    ) -> Dict[str, Any]:
        if not extracted or not extracted.get("items"):
            raise ValueError("No order items were extracted")

        customer = IntentRouter._get_customer(msg.customer_id)
        customer_name = extracted.get("customer_name")
        if not customer_name or str(customer_name).lower() == "unknown":
            customer_name = customer.get("name") or "Unknown"
        delivery_address = extracted.get("delivery_address")
        if not delivery_address or str(delivery_address).lower() == "unknown":
            delivery_address = (
                customer.get("default_address") or customer.get("address") or ""
            )
        customer_phone = extracted.get("customer_phone") or customer.get("phone")

        from app.routes.endpoints import _safe_items_from_extracted

        safe_items = _safe_items_from_extracted(extracted, msg.shop_id)
        valid_items = []
        for item in safe_items:
            item_data = item.model_dump()
            try:
                quantity = float(item_data.get("quantity") or 0)
            except (TypeError, ValueError):
                quantity = 0
            if quantity > 0 and item_data.get("name"):
                valid_items.append(item_data)
        if not valid_items:
            raise ValueError("No valid catalog items with positive quantities")

        from app.services.time_parser import parse_delivery_time

        raw_delivery_time = (
            extracted.get("delivery_time_raw") or extracted.get("delivery_time") or ""
        )
        time_data = parse_delivery_time(raw_delivery_time or msg.raw_text)
        stable_key = f"{msg.channel.value}:{msg.provider_message_id}"
        card_id = f"ac_{hashlib.sha256(stable_key.encode()).hexdigest()[:16]}"
        metadata = dict(msg.metadata)
        metadata.update(
            {
                "inbound_message_id": inbound_id,
                "provider_message_id": msg.provider_message_id,
                "input_channel": msg.channel.value,
                "input_type": msg.message_type.value,
            }
        )

        card_data = {
            "id": card_id,
            "shop_id": msg.shop_id,
            "customer_id": msg.customer_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "delivery_address": delivery_address,
            "delivery_time": time_data.get("normalized") or raw_delivery_time,
            "delivery_time_raw": raw_delivery_time,
            "delivery_time_normalized": time_data.get("normalized"),
            "delivery_time_confidence": time_data.get("confidence", 0.0),
            "delivery_time_warning": time_data.get("warning"),
            "payment_method": extracted.get("payment_method", "UNKNOWN"),
            "items": valid_items,
            "operations": extracted.get("operations", []),
            "status": "pending",
            "source": msg.channel.value,
            "message_type": "ORDER",
            "confidence": extracted.get("confidence", 0.0),
            "metadata": metadata,
            "transcript": msg.raw_text,
        }

        from app.services.confidence_scorer import ConfidenceScorer

        score, label, reasons = ConfidenceScorer.calculate_confidence(card_data)
        card_data["confidence_score"] = score
        card_data["confidence_label"] = label
        card_data["confidence_reasons"] = reasons
        return card_data

    @staticmethod
    def _register_inbound_message(
        msg: NormalizedInboundMessage,
    ) -> Tuple[Optional[str], str]:
        try:
            existing = (
                supabase_client.table("inbound_messages")
                .select("id, processing_status, retry_count")
                .eq("channel", msg.channel.value)
                .eq("provider_message_id", msg.provider_message_id)
                .execute()
            )
            if existing.data:
                record = existing.data[0]
                retry_count = int(record.get("retry_count") or 0)
                if (
                    record.get("processing_status") == "failed"
                    and retry_count < MAX_PROVIDER_RETRIES
                ):
                    claimed = (
                        supabase_client.table("inbound_messages")
                        .update(
                            {
                                "processing_status": "pending",
                                "retry_count": retry_count + 1,
                                "last_error": None,
                                "next_retry_at": None,
                                "processed_at": None,
                            }
                        )
                        .eq("id", record["id"])
                        .eq("processing_status", "failed")
                        .execute()
                    )
                    if claimed.data:
                        return record["id"], "retry"
                return None, "duplicate"

            retention_expires_at = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=30)
            ).isoformat()
            inserted = (
                supabase_client.table("inbound_messages")
                .insert(
                    {
                        "shop_id": msg.shop_id,
                        "customer_id": msg.customer_id,
                        "channel": msg.channel.value,
                        "provider_message_id": msg.provider_message_id,
                        "message_type": msg.message_type.value,
                        "normalized_text": msg.raw_text[:4000],
                        "processing_status": "pending",
                        "retention_expires_at": retention_expires_at,
                    }
                )
                .execute()
            )
            if inserted.data:
                return inserted.data[0]["id"], "new"
        except Exception as exc:
            error_code = getattr(exc, "code", None)
            if error_code == "23505" or "duplicate key value" in str(exc):
                return None, "duplicate"
            logger.error(
                "Inbound registration failed for channel=%s (%s)",
                msg.channel.value,
                type(exc).__name__,
            )
        return None, "error"

    @staticmethod
    def _get_or_create_conversation(
        shop_id: str, customer_id: str, channel: str
    ) -> Optional[Dict[str, Any]]:
        try:
            query = (
                supabase_client.table("customer_conversations")
                .select("*")
                .eq("shop_id", shop_id)
                .eq("customer_id", customer_id)
                .eq("channel", channel)
            )
            result = query.execute()
            if result.data:
                return result.data[0]
            inserted = (
                supabase_client.table("customer_conversations")
                .insert(
                    {
                        "shop_id": shop_id,
                        "customer_id": customer_id,
                        "channel": channel,
                        "state": "idle",
                    }
                )
                .execute()
            )
            if inserted.data:
                return inserted.data[0]
        except Exception as exc:
            if getattr(exc, "code", None) == "23505" or "duplicate key value" in str(
                exc
            ):
                try:
                    result = (
                        supabase_client.table("customer_conversations")
                        .select("*")
                        .eq("shop_id", shop_id)
                        .eq("customer_id", customer_id)
                        .eq("channel", channel)
                        .execute()
                    )
                    if result.data:
                        return result.data[0]
                except Exception:
                    pass
            logger.error(
                "Conversation lookup failed for shop_id=%s (%s)",
                shop_id,
                type(exc).__name__,
            )
        return None

    @staticmethod
    def _conditional_conversation_update(
        conversation_id: str,
        expected_state: str,
        updates: Dict[str, Any],
    ) -> bool:
        try:
            result = (
                supabase_client.table("customer_conversations")
                .update(updates)
                .eq("id", conversation_id)
                .eq("state", expected_state)
                .execute()
            )
            return bool(result.data)
        except Exception as exc:
            logger.error(
                "Conditional conversation update failed for conversation_id=%s (%s)",
                conversation_id,
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _update_conversation(
        conversation_id: str, updates: Dict[str, Any]
    ) -> bool:
        try:
            result = (
                supabase_client.table("customer_conversations")
                .update(updates)
                .eq("id", conversation_id)
                .execute()
            )
            return bool(result.data)
        except Exception as exc:
            logger.error(
                "Conversation update failed for conversation_id=%s (%s)",
                conversation_id,
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _update_inbound_status(
        inbound_id: str,
        status: str,
        detected_intent: Optional[str] = None,
        confidence: Optional[float] = None,
        last_error: Optional[str] = None,
    ) -> bool:
        updates: Dict[str, Any] = {"processing_status": status}
        if detected_intent is not None:
            updates["detected_intent"] = detected_intent
        if confidence is not None:
            updates["confidence"] = confidence
        if last_error is not None:
            updates["last_error"] = str(last_error)[:255]
        if status in TERMINAL_INBOUND_STATUSES:
            updates["processed_at"] = IntentRouter._utc_now()
        if status == "failed":
            updates["next_retry_at"] = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(minutes=5)
            ).isoformat()
        try:
            result = (
                supabase_client.table("inbound_messages")
                .update(updates)
                .eq("id", inbound_id)
                .execute()
            )
            return bool(result.data)
        except Exception as exc:
            logger.error(
                "Inbound status update failed for inbound_id=%s (%s)",
                inbound_id,
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _get_customer(customer_id: str) -> Dict[str, Any]:
        try:
            result = (
                supabase_client.table("customers")
                .select("id, shop_id, name, phone, address")
                .eq("id", customer_id)
                .execute()
            )
            return result.data[0] if result.data else {}
        except Exception:
            return {}

    @staticmethod
    def _get_business_context(
        shop_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        configured = metadata.get("business_context")
        if isinstance(configured, dict):
            return configured
        context: Dict[str, Any] = {"business_type": "general business"}
        try:
            shop = (
                supabase_client.table("shops")
                .select("name")
                .eq("id", shop_id)
                .execute()
            )
            if shop.data:
                context["business_name"] = shop.data[0].get("name")
            catalog = (
                supabase_client.table("catalog_items")
                .select("canonical_name, display_name, category")
                .eq("shop_id", shop_id)
                .eq("is_active", True)
                .limit(50)
                .execute()
            )
            if catalog.data:
                context["offerings"] = [
                    item.get("display_name") or item.get("canonical_name")
                    for item in catalog.data
                    if item.get("display_name") or item.get("canonical_name")
                ]
        except Exception:
            logger.info("Business context fallback used for shop_id=%s", shop_id)
        return context

    @staticmethod
    def _require_owner_id(shop_id: str) -> str:
        owner_id = IntentRouter._get_owner_id(shop_id)
        if not owner_id:
            raise RuntimeError("Shop owner is unavailable")
        return owner_id

    @staticmethod
    def _get_owner_id(shop_id: str) -> Optional[str]:
        try:
            result = (
                supabase_client.table("shops")
                .select("owner_id")
                .eq("id", shop_id)
                .execute()
            )
            if result.data:
                return result.data[0].get("owner_id")
        except Exception:
            pass
        return None

    @staticmethod
    def _is_expired(value: Optional[str]) -> bool:
        if not value:
            return False
        try:
            expires_at = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.datetime.now(datetime.timezone.utc) > expires_at
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _utc_now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
