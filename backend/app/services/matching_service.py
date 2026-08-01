import logging
from typing import Optional, Dict, Any, List
from app.services.supabase import supabase_client
import difflib

logger = logging.getLogger(__name__)

class MatchingService:
    def __init__(self):
        self.supabase = supabase_client

    def match_product(self, raw_name: str, shop_id: str) -> Dict[str, Any]:
        """
        Deterministically match raw_name to catalog items using aliases.
        """
        raw_name_lower = raw_name.lower().strip()
        
        # 1. Fetch catalog items and their aliases for the shop
        try:
            from app.services.catalog_service import catalog_service
            items = catalog_service.get_items_by_shop(shop_id)
            items = [
                item
                for item in items
                if item.get("active", True) and item.get("in_stock", True)
            ]
            if not items:
                return self._unmatched(raw_name)
        except Exception as e:
            logger.error(f"Error fetching catalog items for matching: {e}")
            return self._unmatched(raw_name)

        # 2. Exact match on canonical_name, display_name, or aliases
        for item in items:
            names_to_check = [item.get("canonical_name", "").lower(), item.get("display_name", "").lower()]
            if item.get("english_name"):
                names_to_check.append(item["english_name"].lower())
            aliases = [a.lower() for a in item.get("aliases", [])]
            names_to_check.extend(aliases)
            
            if raw_name_lower in names_to_check:
                return self._matched(raw_name, item)

        # 3. Fuzzy matching
        all_names = {}
        for item in items:
            n1 = item.get("canonical_name", "").lower()
            n2 = item.get("display_name", "").lower()
            if n1: all_names[n1] = item
            if n2: all_names[n2] = item
            if item.get("english_name"):
                all_names[item["english_name"].lower()] = item
            for a in item.get("aliases", []):
                all_names[a.lower()] = item

        matches = difflib.get_close_matches(raw_name_lower, all_names.keys(), n=3, cutoff=0.8)
        if len(matches) == 1:
            matched_item = all_names[matches[0]]
            return self._suggested(raw_name, matched_item)
        elif len(matches) > 1:
            suggestions = [all_names[m].get("display_name") for m in matches]
            return self._ambiguous(raw_name, list(set(suggestions)))
        
        return self._unmatched(raw_name)

    def _matched(self, raw_name: str, item: dict) -> Dict[str, Any]:
        return {
            "raw_name": raw_name,
            "catalog_item_id": item["id"],
            "canonical_name": item["canonical_name"],
            "display_name": item["display_name"],
            "unit": item.get("unit", ""),
            "unit_price": float(item.get("base_price", 0.0)),
            "resolution_status": "matched",
            "possible_matches": []
        }

    def _suggested(self, raw_name: str, item: dict) -> Dict[str, Any]:
        res = self._matched(raw_name, item)
        res["resolution_status"] = "suggested"
        return res

    def _ambiguous(self, raw_name: str, suggestions: List[str]) -> Dict[str, Any]:
        return {
            "raw_name": raw_name,
            "catalog_item_id": None,
            "canonical_name": None,
            "display_name": None,
            "unit": None,
            "unit_price": 0.0,
            "resolution_status": "ambiguous",
            "possible_matches": suggestions
        }

    def _unmatched(self, raw_name: str) -> Dict[str, Any]:
        return {
            "raw_name": raw_name,
            "catalog_item_id": None,
            "canonical_name": None,
            "display_name": None,
            "unit": None,
            "unit_price": 0.0,
            "resolution_status": "unmatched",
            "possible_matches": []
        }

matching_service = MatchingService()
