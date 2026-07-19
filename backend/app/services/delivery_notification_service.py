import logging
from typing import Optional
from app.services.supabase import supabase_client
from app.config.settings import settings
from app.services.bill_link_service import ensure_public_bill_link

logger = logging.getLogger(__name__)

def send_delivery_notification(order_id: str, final_order: Optional[dict] = None) -> dict:
    notification_info = {
        "notification_attempted": True,
        "notification_sent": False,
        "notification_channel": "none",
        "notification_sid": None,
        "notification_status": None,
        "notification_error": None
    }
    
    try:
        print(f"DELIVERY_NOTIFICATION_ENTERED order_id={order_id}", flush=True)
        logger.warning(f"DELIVERY_NOTIFICATION_ENTERED order_id={order_id}")
        
        # Fetch full order if not complete
        if not final_order or "customer_phone" not in final_order:
            full_order_res = supabase_client.table("orders").select("*").eq("id", order_id).execute()
            if not full_order_res.data:
                notification_info["notification_error"] = "Order not found for notification"
                return notification_info
            full_order = full_order_res.data[0]
        else:
            full_order = final_order
            
        debug_info = {
            "order_id": order_id,
            "has_full_order": True,
            "order_keys": list(full_order.keys()),
            "customer_id_present": bool(full_order.get("customer_id")),
            "shop_id_present": bool(full_order.get("shop_id")),
            "customer_phone_present": bool(full_order.get("customer_phone")),
            "action_card_id_present": bool(full_order.get("action_card_id")),
            "total_amount_present": bool(full_order.get("total_amount")),
            "has_twilio_env": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM),
            "has_telegram_env": bool(settings.TELEGRAM_BOT_TOKEN),
            "has_frontend_url": bool(settings.FRONTEND_PUBLIC_BASE_URL)
        }
        print(f"DELIVERY_NOTIFICATION_DEBUG {debug_info}", flush=True)
        logger.warning(f"DELIVERY_NOTIFICATION_DEBUG {debug_info}")
        
        order_id_str = str(order_id)
        customer_id = full_order.get("customer_id")
        shop_id_val = full_order.get("shop_id")
        
        bill_url = ensure_public_bill_link(
            order_id_str,
            shop_id_val,
            db_client=supabase_client,
        )
        total_amount = full_order.get("total_amount", 0)
        bill_msg = f"Your order has been delivered.\nTotal: ₹{total_amount}\nBill: {bill_url}"
        
        # Try to find destination
        channels = []
        if customer_id:
            channels_res = supabase_client.table("customer_channels").select("*").eq("customer_id", customer_id).execute()
            channels = channels_res.data if channels_res.data else []
            
        source = None
        card_phone = None
        telegram_chat_id = None
        action_card_id = full_order.get("action_card_id")
        
        if action_card_id:
            card_res = supabase_client.table("action_cards").select("source, customer_phone, metadata").eq("id", action_card_id).execute()
            if card_res.data:
                card_data = card_res.data[0]
                source = card_data.get("source")
                card_phone = card_data.get("customer_phone")
                meta = card_data.get("metadata") or {}
                if source == "telegram":
                    telegram_chat_id = meta.get("telegram_chat_id")
                    
        whatsapp_channel = None
        meta_whatsapp_channel = None
        telegram_channel = None
        for ch in channels:
            if ch.get("channel") == "whatsapp":
                whatsapp_channel = ch
            elif ch.get("channel") == "meta_whatsapp":
                meta_whatsapp_channel = ch
            elif ch.get("channel") == "telegram":
                telegram_channel = ch
                
        channel_to_use = source
        if not channel_to_use:
            if telegram_channel: channel_to_use = "telegram"
            elif meta_whatsapp_channel: channel_to_use = "meta_whatsapp"
            elif whatsapp_channel: channel_to_use = "whatsapp"
            elif full_order.get("customer_phone"): channel_to_use = "whatsapp"
            
        if channel_to_use == "telegram":
            chat_id = (telegram_channel.get("channel_chat_id") if telegram_channel else None) or telegram_chat_id
            if chat_id:
                from app.services.telegram_service import telegram_service
                telegram_service.send_message(chat_id, bill_msg)
                notification_info["notification_sent"] = True
                notification_info["notification_channel"] = "telegram"
                print(f"DELIVERY_NOTIFICATION_SENT channel=telegram chat_id={chat_id}", flush=True)
                logger.warning(f"DELIVERY_NOTIFICATION_SENT channel=telegram chat_id={chat_id}")
            else:
                notification_info["notification_error"] = "No Telegram chat ID found"
                print("DELIVERY_NOTIFICATION_SKIPPED reason=no_telegram_chat_id", flush=True)
                logger.warning("DELIVERY_NOTIFICATION_SKIPPED reason=no_telegram_chat_id")
        elif channel_to_use == "meta_whatsapp":
            wa_id = (
                meta_whatsapp_channel.get("channel_user_id")
                if meta_whatsapp_channel else None
            )
            phone_number_id = None
            if action_card_id and card_res.data:
                phone_number_id = (
                    (card_res.data[0].get("metadata") or {})
                    .get("meta_phone_number_id")
                )
            if wa_id:
                from app.services.meta_whatsapp_service import meta_whatsapp_service
                result = meta_whatsapp_service.send_text_sync(
                    wa_id, bill_msg, phone_number_id
                )
                notification_info["notification_sent"] = result.get("sent", False)
                notification_info["notification_channel"] = "meta_whatsapp"
                notification_info["notification_sid"] = result.get("message_id")
                notification_info["notification_error"] = result.get("error")
                if result.get("sent"):
                    logger.warning(
                        "DELIVERY_NOTIFICATION_SENT channel=meta_whatsapp message_id=%s",
                        result.get("message_id"),
                    )
                else:
                    logger.warning("DELIVERY_NOTIFICATION_FAILED channel=meta_whatsapp")
            else:
                notification_info["notification_error"] = "No Meta WhatsApp recipient found"
                logger.warning(
                    "DELIVERY_NOTIFICATION_SKIPPED reason=no_meta_whatsapp_recipient"
                )
        elif channel_to_use == "whatsapp":
            phone_to_use = (whatsapp_channel.get("phone") if whatsapp_channel else None) or full_order.get("customer_phone") or card_phone
            if not phone_to_use and customer_id:
                cust_res = supabase_client.table("customers").select("phone").eq("id", customer_id).execute()
                if cust_res.data: phone_to_use = cust_res.data[0].get("phone")
                
            if phone_to_use:
                from app.services.twilio_whatsapp_service import twilio_whatsapp_service
                result = twilio_whatsapp_service.send_whatsapp_message(phone_to_use, bill_msg)
                notification_info["notification_sent"] = result.get("sent", False)
                notification_info["notification_channel"] = "whatsapp"
                notification_info["notification_sid"] = result.get("sid")
                if result.get("error"):
                    notification_info["notification_error"] = result.get("error")
                    print(f"DELIVERY_NOTIFICATION_FAILED safe_error={result.get('error')}", flush=True)
                    logger.warning(f"DELIVERY_NOTIFICATION_FAILED safe_error={result.get('error')}")
                else:
                    print(f"DELIVERY_NOTIFICATION_SENT channel=whatsapp sid={result.get('sid')}", flush=True)
                    logger.warning(f"DELIVERY_NOTIFICATION_SENT channel=whatsapp sid={result.get('sid')}")
            else:
                notification_info["notification_error"] = "No customer phone found"
                print("DELIVERY_NOTIFICATION_SKIPPED reason=no_whatsapp_phone", flush=True)
                logger.warning("DELIVERY_NOTIFICATION_SKIPPED reason=no_whatsapp_phone")
        else:
            notification_info["notification_error"] = "No customer destination found"
            print("DELIVERY_NOTIFICATION_SKIPPED reason=no_customer_destination", flush=True)
            logger.warning("DELIVERY_NOTIFICATION_SKIPPED reason=no_customer_destination")
            
    except Exception as e:
        notification_info["notification_error"] = str(e)
        print(f"DELIVERY_NOTIFICATION_FAILED safe_error={str(e)}", flush=True)
        logger.warning(f"DELIVERY_NOTIFICATION_FAILED safe_error={str(e)}")

    return notification_info
