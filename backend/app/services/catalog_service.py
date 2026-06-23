import logging
import uuid
from datetime import datetime
from typing import List, Optional
from app.services.supabase import supabase_client
from app.schemas.catalog import CatalogItemCreate, CatalogItemUpdate, CatalogItemResponse

logger = logging.getLogger(__name__)

class CatalogService:
    def __init__(self):
        self.supabase = supabase_client
        self.mock_db = []  # For local fallback

    def create_item(self, item_data: CatalogItemCreate) -> Optional[dict]:
        if self.supabase is None:
            # Fallback mock mode
            new_item = item_data.model_dump()
            new_item["id"] = str(uuid.uuid4())
            new_item["created_at"] = datetime.utcnow().isoformat()
            new_item["updated_at"] = datetime.utcnow().isoformat()
            self.mock_db.append(new_item)
            return new_item

        try:
            # Insert into catalog_items
            data = item_data.model_dump(exclude={"aliases"})
            res = self.supabase.table("catalog_items").insert(data).execute()
            if not res.data:
                return None
            item = res.data[0]
            
            # Insert aliases
            if item_data.aliases:
                aliases_data = [
                    {"catalog_item_id": item["id"], "shop_id": item["shop_id"], "alias": a}
                    for a in item_data.aliases
                ]
                self.supabase.table("product_aliases").insert(aliases_data).execute()
            
            item["aliases"] = item_data.aliases
            return item
        except Exception as e:
            logger.error(f"Error creating catalog item: {e}")
            return None

    def get_items_by_shop(self, shop_id: str) -> List[dict]:
        if self.supabase is None:
            return [item for item in self.mock_db if item["shop_id"] == shop_id]

        try:
            res = self.supabase.table("catalog_items").select("*, product_aliases(alias)").eq("shop_id", shop_id).execute()
            if not res.data:
                return []
            # format aliases
            for row in res.data:
                row["aliases"] = [a["alias"] for a in row.get("product_aliases", [])] if row.get("product_aliases") else []
            return res.data
        except Exception as e:
            logger.error(f"Error fetching catalog items: {e}")
            return []

    def update_item(self, item_id: str, item_data: CatalogItemUpdate) -> Optional[dict]:
        if self.supabase is None:
            for item in self.mock_db:
                if item["id"] == item_id:
                    update_dict = item_data.model_dump(exclude_unset=True)
                    item.update(update_dict)
                    item["updated_at"] = datetime.utcnow().isoformat()
                    return item
            return None

        try:
            update_dict = item_data.model_dump(exclude_unset=True, exclude={"aliases"})
            if update_dict:
                res = self.supabase.table("catalog_items").update(update_dict).eq("id", item_id).execute()
                if not res.data:
                    return None
            
            if item_data.aliases is not None:
                # To simplify: delete old and insert new
                # We need shop_id. Fetch item first
                item_res = self.supabase.table("catalog_items").select("shop_id").eq("id", item_id).execute()
                if item_res.data:
                    shop_id = item_res.data[0]["shop_id"]
                    self.supabase.table("product_aliases").delete().eq("catalog_item_id", item_id).execute()
                    if item_data.aliases:
                        aliases_data = [
                            {"catalog_item_id": item_id, "shop_id": shop_id, "alias": a}
                            for a in item_data.aliases
                        ]
                        self.supabase.table("product_aliases").insert(aliases_data).execute()
            
            # Fetch updated item
            res = self.supabase.table("catalog_items").select("*, product_aliases(alias)").eq("id", item_id).execute()
            if res.data:
                row = res.data[0]
                row["aliases"] = [a["alias"] for a in row.get("product_aliases", [])] if row.get("product_aliases") else []
                return row
            return None
        except Exception as e:
            logger.error(f"Error updating catalog item: {e}")
            return None

catalog_service = CatalogService()
