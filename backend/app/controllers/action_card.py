from typing import List, Optional, Dict, Any
from app.services.store import store
from app.schemas.action_card import ActionCard

class ActionCardController:
    @staticmethod
    def get_all_cards() -> List[ActionCard]:
        return store.get_all()

    @staticmethod
    def get_card_by_id(card_id: str) -> Optional[ActionCard]:
        return store.get_by_id(card_id)

    @staticmethod
    def create_card(card_data: Dict[str, Any]) -> ActionCard:
        return store.create(card_data)

    @staticmethod
    def update_card(card_id: str, card_data: Dict[str, Any]) -> Optional[ActionCard]:
        return store.update(card_id, card_data)

    @staticmethod
    def update_card_status(card_id: str, status: str) -> Optional[ActionCard]:
        return store.update_status(card_id, status)

    @staticmethod
    def delete_card(card_id: str) -> bool:
        return store.delete(card_id)
