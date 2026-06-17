from supabase import create_client, Client
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

supabase_client: Client = None

if (settings.SUPABASE_URL and settings.SUPABASE_URL != "your-supabase-url-here" and
    settings.SUPABASE_KEY and settings.SUPABASE_KEY != "your-supabase-anon-key-here"):
    try:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
else:
    logger.warning("Supabase URL or Key is missing. Database functionalities will fallback to mock local database.")

class SupabaseService:
    @staticmethod
    def is_available() -> bool:
        return supabase_client is not None

    @staticmethod
    def create(card_data: dict) -> dict:
        if not supabase_client: return None
        try:
            res = supabase_client.table("action_cards").insert(card_data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Supabase create error: {e}")
            return None

    @staticmethod
    def get_all(user_id: str = None) -> list:
        if not supabase_client: return []
        try:
            query = supabase_client.table("action_cards").select("*")
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.order("created_at", desc=True).execute()
            return res.data
        except Exception as e:
            logger.error(f"Supabase get_all error: {e}")
            return []

    @staticmethod
    def get_by_id(card_id: str, user_id: str = None) -> dict:
        if not supabase_client: return None
        try:
            query = supabase_client.table("action_cards").select("*").eq("id", card_id)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Supabase get_by_id error: {e}")
            return None

    @staticmethod
    def update(card_id: str, card_data: dict, user_id: str = None) -> dict:
        if not supabase_client: return None
        try:
            query = supabase_client.table("action_cards").update(card_data).eq("id", card_id)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Supabase update error: {e}")
            return None

    @staticmethod
    def delete(card_id: str, user_id: str = None) -> bool:
        if not supabase_client: return False
        try:
            query = supabase_client.table("action_cards").delete().eq("id", card_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
            return True
        except Exception as e:
            logger.error(f"Supabase delete error: {e}")
            return False
