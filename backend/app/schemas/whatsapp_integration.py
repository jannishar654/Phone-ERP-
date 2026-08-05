from typing import Optional

from pydantic import BaseModel, Field, SecretStr, field_validator


class WhatsAppOnboardingSessionResponse(BaseModel):
    state: str
    app_id: str
    configuration_id: str
    graph_api_version: str
    expires_in_seconds: int


class WhatsAppOnboardingCallbackRequest(BaseModel):
    state: str = Field(min_length=32, max_length=256)
    code: str = Field(min_length=8, max_length=4096)
    # These are selection hints from Meta's signed signup result. The backend
    # still verifies both values against the assets granted by the token.
    waba_id: Optional[str] = Field(default=None, max_length=128)
    phone_number_id: Optional[str] = Field(default=None, max_length=128)
    # Used once to register the Cloud API phone and enable two-step
    # verification. It is never persisted or returned.
    registration_pin: SecretStr

    @field_validator("registration_pin")
    @classmethod
    def validate_registration_pin(cls, value: SecretStr) -> SecretStr:
        pin = value.get_secret_value()
        if len(pin) != 6 or any(character < "0" or character > "9" for character in pin):
            raise ValueError("Registration PIN must contain exactly six digits")
        return value


class WhatsAppConnectionStatusResponse(BaseModel):
    embedded_signup_enabled: bool
    configured: bool
    status: str
    display_phone_number: Optional[str] = None
    verified_name: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    last_webhook_at: Optional[str] = None
    last_health_check_at: Optional[str] = None
    last_error: Optional[str] = None
    connected_at: Optional[str] = None
    token_expires_at: Optional[str] = None


class WhatsAppHealthCheckResponse(BaseModel):
    healthy: bool
    status: str
    display_phone_number: Optional[str] = None
    verified_name: Optional[str] = None
