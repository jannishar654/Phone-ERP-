from typing import List, Optional, Dict, Any
from app.services.store import store
from app.services.supabase import SupabaseService
from app.schemas.action_card import ActionCard, Item
import uuid
from datetime import datetime

class ActionCardController:
    @staticmethod
    def get_all_cards(user_id: Optional[str] = None) -> List[ActionCard]:
        if SupabaseService.is_available():
            data = SupabaseService.get_all(user_id)
            return [ActionCardController._parse_supabase_card(c) for c in data]
        return store.get_all()

    @staticmethod
    def get_card_by_id(card_id: str, user_id: Optional[str] = None) -> Optional[ActionCard]:
        if SupabaseService.is_available():
            data = SupabaseService.get_by_id(card_id, user_id)
            return ActionCardController._parse_supabase_card(data) if data else None
        return store.get_by_id(card_id)

    @staticmethod
    def create_card(card_data: Dict[str, Any], user_id: Optional[str] = None) -> ActionCard:
        if user_id:
            card_data["user_id"] = user_id
            
        if SupabaseService.is_available():
            card_id = card_data.get("id") or f"ac_{uuid.uuid4().hex[:8]}"
            items = card_data.get("items", [])
            items_dict = [i.model_dump() if hasattr(i, "model_dump") else i for i in items]
            
            insert_data = {
                "id": card_id,
                "user_id": card_data.get("user_id"),
                "customer_name": card_data.get("customer_name"),
                "customer_phone": card_data.get("customer_phone"),
                "items": items_dict,
                "delivery_address": card_data.get("delivery_address"),
                "delivery_time": card_data.get("delivery_time"),
                "delivery_time_raw": card_data.get("delivery_time_raw"),
                "delivery_time_normalized": card_data.get("delivery_time_normalized"),
                "delivery_time_confidence": card_data.get("delivery_time_confidence"),
                "delivery_time_warning": card_data.get("delivery_time_warning"),
                "risk_flags": card_data.get("risk_flags", []),
                "missing_fields": card_data.get("missing_fields", []),
                "validation_warnings": card_data.get("validation_warnings", []),
                "payment_method": card_data.get("payment_method", "Not Specified"),
                "status": card_data.get("status", "pending"),
                "source": card_data.get("source", "text"),
                "transcript": card_data.get("transcript", "Manual order entry")
            }
            # Remove None values to let DB defaults apply
            insert_data = {k: v for k, v in insert_data.items() if v is not None}
            
            result = SupabaseService.create(insert_data)
            return ActionCardController._parse_supabase_card(result) if result else store.create(card_data)
        
        return store.create(card_data)

    @staticmethod
    def update_card(card_id: str, card_data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[ActionCard]:
        if SupabaseService.is_available():
            update_data = {k: v for k, v in card_data.items() if k not in ["id", "created_at", "updated_at", "user_id"]}
            if "items" in update_data:
                update_data["items"] = [i.model_dump() if hasattr(i, "model_dump") else i for i in update_data["items"]]
            result = SupabaseService.update(card_id, update_data, user_id)
            return ActionCardController._parse_supabase_card(result) if result else None
            
        return store.update(card_id, card_data)

    @staticmethod
    def update_card_status(card_id: str, status: str, user_id: Optional[str] = None) -> Optional[ActionCard]:
        if SupabaseService.is_available():
            result = SupabaseService.update(card_id, {"status": status}, user_id)
            return ActionCardController._parse_supabase_card(result) if result else None
        return store.update_status(card_id, status)

    @staticmethod
    def delete_card(card_id: str, user_id: Optional[str] = None) -> bool:
        if SupabaseService.is_available():
            return SupabaseService.delete(card_id, user_id)
        return store.delete(card_id)

    @staticmethod
    def _parse_supabase_card(data: dict) -> ActionCard:
        items = data.get("items") or []
        parsed_items = [Item(**i) if isinstance(i, dict) else i for i in items]
        data["items"] = parsed_items
        return ActionCard(**data)
