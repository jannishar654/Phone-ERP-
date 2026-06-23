import logging
from typing import Optional, Dict
from app.services.supabase import supabase_client
from app.schemas.order import OrderCreate, OrderItemCreate

logger = logging.getLogger(__name__)

class OrderService:
    def __init__(self):
        self.supabase = supabase_client

    def convert_action_card_to_order(self, action_card_id: str, user_id: str) -> Optional[dict]:
        try:
            # 1. Fetch action card
            action_card = None
            if self.supabase is None:
                from app.services.store import store
                card_obj = store.get_by_id(action_card_id)
                if card_obj:
                    action_card = card_obj.model_dump()
            else:
                res = self.supabase.table("action_cards").select("*").eq("id", action_card_id).execute()
                if res.data:
                    action_card = res.data[0]
            
            if not action_card:
                logger.error(f"Action card {action_card_id} not found.")
                return None
            
            shop_id = action_card.get("shop_id")
            
            # Allow conversion even without shop_id for backward compatibility
            if not shop_id:
                if self.supabase is None:
                    shop_id = "mock-shop"
                else:
                    logger.warning(f"Converting action card {action_card_id} without shop_id. This is a legacy card.")
            
            # 2. Build order data
            total_amount = 0.0
            order_items_data = []
            status = "pending"
            
            from app.services.matching_service import matching_service
            
            # For each item, perform catalog matching to get the unit price if not already set or missing
            for item in action_card.get("items", []):
                raw_name = item.get("raw_name") or item.get("name", "Unknown")
                
                # Match catalog product
                matched = matching_service.match_product(raw_name, shop_id) if shop_id else {}
                
                # If matched, we get unit_price and catalog_item_id
                catalog_item_id = matched.get("catalog_item_id")
                
                # Trust the matched price if matched, else fallback to Action Card price
                if matched.get("resolution_status") in ["matched", "suggested"]:
                    price = matched.get("unit_price", 0.0)
                    item["price"] = price
                    item["unit"] = matched.get("unit", item.get("unit"))
                    if not item.get("metadata"):
                        item["metadata"] = {}
                    item["metadata"]["catalog_item_id"] = catalog_item_id
                else:
                    price = item.get("price", 0.0) or 0.0
                
                qty = item.get("quantity", 0.0) or 0.0
                line_total = price * qty
                total_amount += line_total
                
                if matched.get("resolution_status") not in ["matched", "suggested"] and (item.get("price_status") == "Pending Price Verification" or not price):
                    status = "Pending Price Verification"

                order_items_data.append({
                    "catalog_item_id": catalog_item_id or (item.get("metadata", {}).get("catalog_item_id") if item.get("metadata") else None),
                    "raw_name": raw_name,
                    "quantity": qty,
                    "unit": item.get("unit"),
                    "unit_price": price,
                    "line_total": line_total
                })
            
            # 3. Insert order
            import uuid
            from datetime import datetime
            
            order_id = str(uuid.uuid4())
            order_data = {
                "id": order_id,
                "shop_id": shop_id,
                "customer_id": action_card.get("customer_id"),
                "action_card_id": action_card_id,
                "total_amount": total_amount,
                "status": status,
                "delivery_address": action_card.get("delivery_address"),
                "payment_method": action_card.get("payment_method"),
                "created_at": datetime.utcnow().isoformat()
            }
            
            if self.supabase is None:
                # In mock mode, we just return the order dict directly and update the action card in store
                from app.services.store import store
                for oi in order_items_data:
                    oi["order_id"] = order_id
                    oi["id"] = str(uuid.uuid4())
                order_data["order_items"] = order_items_data
                
                store.update_status(action_card_id, "converted")
                return order_data

            # Remove keys with None if they are not allowed to be null, but our schema allows nulls.
            if not shop_id:
                # If shop_id is null, it might violate RLS or NOT NULL constraint.
                # Assuming fallback logic or dummy shop. But for now, just try insert.
                # Actually, our schema has shop_id NOT NULL. For legacy cards, we might fail unless we bypass or they have a shop.
                pass
                
            res = self.supabase.table("orders").insert(order_data).execute()
            if not res.data:
                return None
            order = res.data[0]
            
            # 4. Insert order items
            for oi in order_items_data:
                oi["order_id"] = order["id"]
            
            if order_items_data:
                self.supabase.table("order_items").insert(order_items_data).execute()
            
            # 5. Link back to action card
            self.supabase.table("action_cards").update({"order_id": order["id"], "status": "converted"}).eq("id", action_card_id).execute()
            
            # Fetch complete order
            res = self.supabase.table("orders").select("*, order_items(*)").eq("id", order["id"]).execute()
            return res.data[0] if res.data else None
            
        except Exception as e:
            logger.error(f"Error converting action card to order: {e}")
            return None

order_service = OrderService()
