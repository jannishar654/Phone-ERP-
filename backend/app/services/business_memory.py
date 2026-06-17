import json
import os
import difflib
from collections import ChainMap
import logging
from typing import Dict, List, Any

# TODO: For production, migrate 'aliases.json' mapping to Supabase `products` and `product_aliases` tables.
# The SQL schema is provided in backend/sql/products.sql.

logger = logging.getLogger(__name__)

class BusinessMemoryResolver:
    """
    A lightweight business-memory layer using ChainMap to resolve product aliases
    into standardized inventory names. 
    """
    
    def __init__(self, data_path: str = None):
        if data_path is None:
            # Default to backend/app/data/aliases.json
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(base_dir, "data", "aliases.json")
            
        self.data_path = data_path
        self.local_aliases = {}
        self.customer_aliases = {}
        self.load_data()
        
    def load_data(self):
        """Loads the JSON-based aliases into memory."""
        if not os.path.exists(self.data_path):
            logger.warning(f"Alias data file not found at {self.data_path}. Using empty dictionaries.")
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.local_aliases = data.get("local_aliases", {})
                self.customer_aliases = data.get("customer_aliases", {})
        except Exception as e:
            logger.error(f"Error loading aliases from {self.data_path}: {e}")

    def reload(self):
        """Reloads the data from the file."""
        self.load_data()

    def save_data(self):
        """Saves the current memory dictionaries back to the JSON file."""
        data = {
            "local_aliases": self.local_aliases,
            "customer_aliases": self.customer_aliases
        }
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Successfully saved updated aliases to disk.")
        except Exception as e:
            logger.error(f"Failed to save aliases: {e}")

    def add_customer_alias(self, customer_id: str, raw_name: str, standard_name: str):
        """Dynamically adds or updates a specific customer alias and saves to disk."""
        if customer_id not in self.customer_aliases:
            self.customer_aliases[customer_id] = {}
        
        normalized_raw = raw_name.strip().lower()
        self.customer_aliases[customer_id][normalized_raw] = standard_name.strip()
        self.save_data()

    def add_local_alias(self, raw_name: str, standard_name: str):
        """Dynamically adds or updates a local regional alias and saves to disk."""
        normalized_raw = raw_name.strip().lower()
        self.local_aliases[normalized_raw] = standard_name.strip()
        self.save_data()

    def resolve_product(self, raw_name: str, customer_id: str = None) -> str:
        """
        Resolves a raw product name into a standard inventory name using a ChainMap.
        Checks customer-specific aliases first, then local/regional aliases.
        """
        if not raw_name:
            return raw_name

        normalized_raw = raw_name.strip().lower()
        
        # Get customer specific dict if customer_id provided
        specific_customer_dict = {}
        if customer_id and customer_id in self.customer_aliases:
            specific_customer_dict = self.customer_aliases[customer_id]

        # ChainMap prioritizes dictionaries in the order they are passed
        memory = ChainMap(specific_customer_dict, self.local_aliases)
        
        # 1. Exact Match Check
        if normalized_raw in memory:
            return memory[normalized_raw]
            
        # 2. Fuzzy Match (using difflib to maintain backward compatibility with old aliases.py logic)
        # We search across all keys in the ChainMap with a high cutoff to prevent false positives (e.g. tamatar -> aata)
        all_keys = list(memory.keys())
        matches = difflib.get_close_matches(normalized_raw, all_keys, n=1, cutoff=0.85)
        
        if matches:
            best_match = matches[0]
            return memory[best_match]
            
        # 3. No match found, return the original raw string
        return raw_name.strip()

    def resolve_product_detailed(self, raw_name: str, customer_id: str = None) -> dict:
        """
        Resolves a raw product name and returns matching metadata for the UI warning system.
        """
        if not raw_name:
            return {"name": raw_name, "matched": False, "possible_matches": []}

        normalized_raw = raw_name.strip().lower()
        
        specific_customer_dict = {}
        if customer_id and customer_id in self.customer_aliases:
            specific_customer_dict = self.customer_aliases[customer_id]

        memory = ChainMap(specific_customer_dict, self.local_aliases)
        
        if normalized_raw in memory:
            return {"name": memory[normalized_raw], "matched": True, "possible_matches": []}
            
        all_keys = list(memory.keys())
        
        # High confidence match
        strict_matches = difflib.get_close_matches(normalized_raw, all_keys, n=1, cutoff=0.85)
        if strict_matches:
            return {"name": memory[strict_matches[0]], "matched": True, "possible_matches": []}
            
        # Low confidence match (possible suggestions)
        loose_matches = difflib.get_close_matches(normalized_raw, all_keys, n=3, cutoff=0.5)
        possible_suggestions = list(set([memory[m] for m in loose_matches]))
        
        return {
            "name": raw_name.strip(), 
            "matched": False, 
            "possible_matches": possible_suggestions
        }

    def resolve_customer(self, raw_name: str) -> str:
        """
        Resolves a raw customer name alias into the standard customer name.
        """
        if not raw_name:
            return raw_name
            
        normalized_raw = raw_name.strip().lower()
        
        # 1. Exact Match
        if normalized_raw in self.customer_aliases:
            # We are assuming the root customer_aliases maps string -> string for generic aliases
            val = self.customer_aliases[normalized_raw]
            if isinstance(val, str):
                return val
                
        # 2. Fuzzy Match
        str_keys = [k for k, v in self.customer_aliases.items() if isinstance(v, str)]
        matches = difflib.get_close_matches(normalized_raw, str_keys, n=1, cutoff=0.85)
        
        if matches:
            return self.customer_aliases[matches[0]]
            
        return raw_name.strip()

# Create a singleton instance for use across the application
business_memory = BusinessMemoryResolver()
