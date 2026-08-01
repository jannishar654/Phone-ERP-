import logging
from typing import Any, Dict, List, Optional, Union

from app.config.business_defaults import (
    BUSINESS_DEFAULTS,
    CANONICAL_TRANSITIONS,
    get_business_default,
)
from app.schemas.business_config import BusinessConfiguration, BusinessType
from app.services.supabase import supabase_client


logger = logging.getLogger(__name__)


class BusinessConfigService:
    def _fallback(self, shop_id: str) -> BusinessConfiguration:
        return BusinessConfiguration(
            shop_id=shop_id,
            id=f"fallback-{shop_id}",
            created_at="2000-01-01T00:00:00Z",
            updated_at="2000-01-01T00:00:00Z",
            **get_business_default(BusinessType.grocery.value),
        )

    @staticmethod
    def normalize_business_type(value: Union[BusinessType, str]) -> BusinessType:
        try:
            return value if isinstance(value, BusinessType) else BusinessType(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported business type: {value}") from exc

    def get_config(self, shop_id: str) -> BusinessConfiguration:
        """Fetch active configuration, preserving grocery behavior on failure."""
        if not supabase_client:
            return self._fallback(shop_id)

        try:
            result = (
                supabase_client.table("business_configurations")
                .select("*")
                .eq("shop_id", shop_id)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            if result.data:
                return BusinessConfiguration(**result.data[0])
        except Exception as exc:
            logger.warning(
                "Business configuration fallback used for shop_id=%s (%s)",
                shop_id,
                type(exc).__name__,
            )
        return self._fallback(shop_id)

    def create_default_config(
        self, shop_id: str, business_type: Union[BusinessType, str] = BusinessType.grocery
    ) -> BusinessConfiguration:
        """Create once and recover safely if concurrent requests race."""
        selected_type = self.normalize_business_type(business_type)
        if not supabase_client:
            return BusinessConfiguration(
                shop_id=shop_id,
                id="mock-config",
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:00:00Z",
                **get_business_default(selected_type.value),
            )

        existing = self.get_config(shop_id)
        if not existing.id.startswith("fallback-"):
            return existing

        payload = get_business_default(selected_type.value)
        payload["shop_id"] = shop_id
        try:
            result = (
                supabase_client.table("business_configurations")
                .insert(payload)
                .execute()
            )
            if result.data:
                return BusinessConfiguration(**result.data[0])
        except Exception as exc:
            # The partial unique index can reject the losing side of a race.
            logger.info(
                "Business configuration insert raced for shop_id=%s (%s)",
                shop_id,
                type(exc).__name__,
            )

        recovered = self.get_config(shop_id)
        if not recovered.id.startswith("fallback-"):
            return recovered
        raise RuntimeError("Business configuration could not be provisioned")

    def get_workflow_stages(self, shop_id: str) -> List[str]:
        return self.get_config(shop_id).workflow_stages

    def is_valid_transition(
        self, shop_id: str, current_status: Optional[str], new_status: str
    ) -> bool:
        config = self.get_config(shop_id)
        transitions = config.settings.get(
            "workflow_transitions", CANONICAL_TRANSITIONS
        )
        current = current_status or "pending_review"
        return new_status in transitions.get(current, [])

    def build_extraction_context(self, shop_id: str) -> Dict[str, Any]:
        """Build a bounded, prompt-safe context from validated configuration."""
        config = self.get_config(shop_id)
        raw_context = config.extraction_context or {}
        context: Dict[str, Any] = {
            "business_type": config.business_type.value,
            "display_name": (config.display_name or config.business_type.value)[:120],
            "required_order_fields": config.required_order_fields[:20],
            "optional_order_fields": config.optional_order_fields[:20],
            "terminology": dict(list(config.terminology.items())[:20]),
            "default_unit": str(raw_context.get("default_unit", "piece"))[:40],
            "allow_partial_quantities": bool(
                raw_context.get("allow_partial_quantities", True)
            ),
            "common_items_hint": str(
                raw_context.get("common_items_hint", "")
            )[:500],
        }
        return context


business_config_service = BusinessConfigService()
