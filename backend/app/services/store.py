from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from app.schemas.action_card import ActionCard, Item

class InMemoryStore:
    def __init__(self):
        self._db: Dict[str, ActionCard] = {}
        self._seed_initial_data()

    def _seed_initial_data(self):
        # Seed initial mock data matching frontend layouts
        initial_cards = [
            ActionCard(
                id="ac_01h9b82c",
                customer_name="Johnathan Archer",
                customer_phone="+1 310-555-2150",
                items=[
                    Item(name="Plasma Injector Model D", quantity=2, price=450.00),
                    Item(name="Dilithium Crystal Shards (Grade A)", quantity=5, price=1200.00)
                ],
                delivery_address="Warp Nacelle Bay, Dock 4, Starbase 1",
                delivery_time="Stardate 58432.1 (Friday morning)",
                status="pending",
                source="audio",
                transcript="Yeah, this is Captain Archer. We need two of those Plasma Injectors, model D, and five grade-A dilithium crystal shards delivered to Dock 4 at Starbase 1 by Friday morning. Charge it to Starfleet Command.",
                created_at=datetime.utcnow()
            ),
            ActionCard(
                id="ac_01h9b83f",
                customer_name="Ellen Ripley",
                customer_phone="+1 800-555-8299",
                items=[
                    Item(name="M41A Pulse Rifle", quantity=4, price=899.99),
                    Item(name="Incendiary Ammo Crates", quantity=2, price=150.00)
                ],
                delivery_address="USS Sulaco Cargo Bay 2",
                delivery_time="ASAP before launch",
                status="processing",
                source="audio",
                transcript="This is Ripley, Nostromo officer. We need immediate delivery of four M41A Pulse Rifles and two crates of incendiary ammunition. Send it straight to Cargo Bay 2 on the Sulaco. Hurry up, we are running out of time.",
                created_at=datetime.utcnow()
            ),
            ActionCard(
                id="ac_01h9b84g",
                customer_name="Arthur Dent",
                customer_phone="+44 20-7946-0922",
                items=[
                    Item(name="Electronic Towel (Microfiber)", quantity=1, price=42.00),
                    Item(name="Nutri-Matic Tea Dispenser", quantity=1, price=120.00)
                ],
                delivery_address="Megadodo Publications, Islington, London",
                delivery_time="Next Thursday morning",
                status="completed",
                source="text",
                transcript="I'd like to place an order for one microfiber electronic towel and one Nutri-Matic tea dispenser. Delivery address is Megadodo Publications in London. Needs to arrive next Thursday, because they are demolishing my house next Thursday.",
                created_at=datetime.utcnow()
            ),
            ActionCard(
                id="ac_9a82b1",
                customer_name="Sarah Connor",
                customer_phone="+1 415-555-0199",
                items=[
                    Item(name="RAM Modules", quantity=2, price=80.00),
                    Item(name="Core i9 CPU", quantity=1, price=500.00)
                ],
                delivery_address="742 Evergreen Terrace, San Francisco, CA",
                delivery_time="Tomorrow, 2:00 PM",
                status="pending",
                source="audio",
                transcript="Hello, I need two RAM modules and one Core i9 CPU delivered to 742 Evergreen Terrace, San Francisco by tomorrow at 2:00 PM. Name is Sarah Connor.",
                created_at=datetime.utcnow()
            ),
            ActionCard(
                id="ac_4f31c8",
                customer_name="Bruce Wayne",
                customer_phone="+1 607-555-0143",
                items=[
                    Item(name="Carbon Fiber Plates", quantity=10, price=250.00)
                ],
                delivery_address="1007 Mountain Drive, Gotham",
                delivery_time="Monday morning",
                status="processing",
                source="text",
                transcript="I require 10 carbon fiber plates delivered to 1007 Mountain Drive, Gotham on Monday morning.",
                created_at=datetime.utcnow()
            ),
            ActionCard(
                id="ac_7d92e5",
                customer_name="Tony Stark",
                customer_phone="+1 310-555-0182",
                items=[
                    Item(name="Palladium Core Reactor", quantity=1, price=10000.00)
                ],
                delivery_address="10880 Malibu Point, CA",
                delivery_time="Immediate",
                status="delivered",
                source="audio",
                transcript="Hey, order me one Palladium Core Reactor immediately. Delivery to 10880 Malibu Point, CA. Make it fast.",
                created_at=datetime.utcnow()
            )
        ]
        for card in initial_cards:
            self._db[card.id] = card

    def get_all(self) -> List[ActionCard]:
        return sorted(self._db.values(), key=lambda x: x.created_at, reverse=True)

    def get_by_id(self, card_id: str) -> Optional[ActionCard]:
        return self._db.get(card_id)

    def create(self, card_data: Dict[str, Any]) -> ActionCard:
        card_id = card_data.get("id") or f"ac_{uuid.uuid4().hex[:8]}"
        items_data = card_data.get("items", [])
        items = [Item(**item) if isinstance(item, dict) else item for item in items_data]
        
        new_card = ActionCard(
            id=card_id,
            user_id=card_data.get("user_id"),
            customer_name=card_data.get("customer_name"),
            customer_phone=card_data.get("customer_phone"),
            items=items,
            delivery_address=card_data.get("delivery_address"),
            delivery_time=card_data.get("delivery_time"),
            delivery_time_raw=card_data.get("delivery_time_raw"),
            delivery_time_normalized=card_data.get("delivery_time_normalized"),
            delivery_time_confidence=card_data.get("delivery_time_confidence"),
            delivery_time_warning=card_data.get("delivery_time_warning"),
            delivery_address_raw=card_data.get("delivery_address_raw"),
            risk_flags=card_data.get("risk_flags", []),
            missing_fields=card_data.get("missing_fields", []),
            validation_warnings=card_data.get("validation_warnings", []),
            payment_method=card_data.get("payment_method", "Not Specified"),
            status=card_data.get("status", "pending"),
            source=card_data.get("source", "text"),
            message_type=card_data.get("message_type", "ORDER"),
            confidence=card_data.get("confidence"),
            stt_provider=card_data.get("stt_provider"),
            extraction_provider=card_data.get("extraction_provider"),
            metadata=card_data.get("metadata", {}),
            transcript=card_data.get("transcript", "Manual order entry"),
            created_at=datetime.utcnow()
        )
        self._db[card_id] = new_card
        return new_card

    def update(self, card_id: str, card_data: Dict[str, Any]) -> Optional[ActionCard]:
        if card_id not in self._db:
            return None
        
        card = self._db[card_id]
        if "customer_name" in card_data:
            card.customer_name = card_data["customer_name"]
        if "customer_phone" in card_data:
            card.customer_phone = card_data["customer_phone"]
        if "delivery_address" in card_data:
            card.delivery_address = card_data["delivery_address"]
        if "delivery_time" in card_data:
            card.delivery_time = card_data["delivery_time"]
        if "delivery_time_raw" in card_data:
            card.delivery_time_raw = card_data["delivery_time_raw"]
        if "delivery_time_normalized" in card_data:
            card.delivery_time_normalized = card_data["delivery_time_normalized"]
        if "delivery_time_confidence" in card_data:
            card.delivery_time_confidence = card_data["delivery_time_confidence"]
        if "delivery_time_warning" in card_data:
            card.delivery_time_warning = card_data["delivery_time_warning"]
        if "delivery_address_raw" in card_data:
            card.delivery_address_raw = card_data["delivery_address_raw"]
        if "risk_flags" in card_data:
            card.risk_flags = card_data["risk_flags"]
        if "missing_fields" in card_data:
            card.missing_fields = card_data["missing_fields"]
        if "validation_warnings" in card_data:
            card.validation_warnings = card_data["validation_warnings"]
        if "payment_method" in card_data:
            card.payment_method = card_data["payment_method"]
        if "status" in card_data:
            card.status = card_data["status"]
        if "source" in card_data:
            card.source = card_data["source"]
        if "message_type" in card_data:
            card.message_type = card_data["message_type"]
        if "confidence" in card_data:
            card.confidence = card_data["confidence"]
        if "stt_provider" in card_data:
            card.stt_provider = card_data["stt_provider"]
        if "extraction_provider" in card_data:
            card.extraction_provider = card_data["extraction_provider"]
        if "metadata" in card_data:
            card.metadata = card_data["metadata"]
        if "transcript" in card_data:
            card.transcript = card_data["transcript"]
        if "items" in card_data:
            items_data = card_data["items"]
            card.items = [Item(**item) if isinstance(item, dict) else item for item in items_data]
            
        self._db[card_id] = card
        return card

    def update_status(self, card_id: str, status: str) -> Optional[ActionCard]:
        if card_id not in self._db:
            return None
        card = self._db[card_id]
        card.status = status
        self._db[card_id] = card
        return card

    def delete(self, card_id: str) -> bool:
        if card_id not in self._db:
            return False
        del self._db[card_id]
        return True

store = InMemoryStore()
