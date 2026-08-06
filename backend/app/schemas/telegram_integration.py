from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class TelegramConnectRequest(BaseModel):
    bot_token: SecretStr = Field(description="Bot token issued by Telegram BotFather")


class TelegramConnectionStatusResponse(BaseModel):
    configured: bool
    status: str
    bot_id: Optional[str] = None
    bot_username: Optional[str] = None
    bot_display_name: Optional[str] = None
    last_webhook_at: Optional[str] = None
    last_health_check_at: Optional[str] = None
    last_error: Optional[str] = None
    connected_at: Optional[str] = None


class TelegramHealthCheckResponse(BaseModel):
    healthy: bool
    status: str
    bot_username: Optional[str] = None
    pending_update_count: int = 0
