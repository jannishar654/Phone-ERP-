from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union, Any, Optional
import os

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # CORS origins
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://phone-erp.vercel.app",
    ]
    CORS_ORIGIN_REGEX: Optional[str] = r"https://phone-erp(?:-[a-z0-9-]+)?\.vercel\.app"
    
    SUPABASE_URL: str = "your-supabase-url-here"
    SUPABASE_KEY: str = "your-supabase-anon-key-here"
    # Server-only. Prefer this on Render; never expose it to Next.js.
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    
    GEMINI_API_KEY: str = "your-gemini-api-key-here"
    SARVAM_API_KEY: str = ""
    
    # Providers
    STT_PROVIDER: str = "sarvam"
    EXTRACTION_PROVIDER: str = "gemini"
    ENABLE_OLLAMA: bool = False
    BUSINESS_ALIAS_MODE: str = "off"
    # Enable fallback Layer 2 LLM Normalizer for messy hinglish
    ENABLE_LLM_FALLBACK: bool = True
    # Enable One-Call LLM Transliteration for Devanagari ASR transcripts
    ENABLE_LLM_TRANSLITERATION: bool = False

    # Security: Require JWT Auth for backend routes
    REQUIRE_AUTH: bool = False

    # Telegram Integration
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_DEFAULT_OWNER_ID: Optional[str] = None
    TELEGRAM_DEFAULT_SHOP_ID: Optional[str] = None
    TELEGRAM_DEFAULT_OWNER_EMAIL: Optional[str] = None
    # Public backend origin used when registering per-business Telegram
    # webhooks, for example https://phone-erp-1.onrender.com.
    TELEGRAM_WEBHOOK_BASE_URL: str = ""

    # Twilio WhatsApp Integration
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    TWILIO_DEFAULT_OWNER_ID: Optional[str] = None
    TWILIO_DEFAULT_SHOP_ID: Optional[str] = None

    # Meta WhatsApp Cloud API (server-only)
    META_WHATSAPP_ACCESS_TOKEN: str = ""
    META_WHATSAPP_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_WABA_ID: str = ""
    META_WHATSAPP_VERIFY_TOKEN: str = ""
    META_APP_SECRET: str = ""
    META_GRAPH_API_VERSION: str = "v25.0"
    # Pilot fallback only. Multi-tenant routing should use whatsapp_connections.
    META_WHATSAPP_DEFAULT_SHOP_ID: Optional[str] = None
    META_WHATSAPP_ALLOW_DEFAULT_CONNECTION_FALLBACK: bool = False
    META_WHATSAPP_MAX_WEBHOOK_BYTES: int = 1024 * 1024
    META_WHATSAPP_MAX_MEDIA_BYTES: int = 15 * 1024 * 1024
    META_WHATSAPP_WORKER_BATCH_SIZE: int = 10
    META_WHATSAPP_WORKER_POLL_SECONDS: float = 2.0
    META_WHATSAPP_RETRY_BASE_SECONDS: int = 30
    # Multi-business Embedded Signup. Keep disabled until Meta App Review and
    # the database migration are complete.
    META_WHATSAPP_EMBEDDED_SIGNUP_ENABLED: bool = False
    # Comma-separated shop UUIDs allowed into the supervised pilot. Use "*"
    # only after Meta approval when self-service onboarding is ready.
    META_WHATSAPP_EMBEDDED_SIGNUP_ALLOWED_SHOP_IDS: Union[List[str], str] = []
    META_APP_ID: str = ""
    META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID: str = ""
    # URL-safe base64 encoded 32-byte AES key. This encrypts per-business
    # credentials at rest and must exist only on the backend.
    META_WHATSAPP_TOKEN_ENCRYPTION_KEY: str = ""
    META_WHATSAPP_TOKEN_KEY_VERSION: int = 1
    # Preferred shared key for newly connected provider credentials. Existing
    # deployments safely fall back to the Meta key until this is configured.
    INTEGRATION_CREDENTIAL_ENCRYPTION_KEY: str = ""
    INTEGRATION_CREDENTIAL_KEY_VERSION: int = 1
    
    # Public Bill Configuration
    FRONTEND_PUBLIC_BASE_URL: str = "http://localhost:3000"
    BILL_LINK_SIGNING_SECRET: str = "default-secret-change-in-production"
    CUSTOMER_PORTAL_SIGNING_SECRET: Optional[str] = None
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("META_WHATSAPP_EMBEDDED_SIGNUP_ALLOWED_SHOP_IDS", mode="before")
    @classmethod
    def parse_embedded_signup_shop_ids(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            return [shop_id.strip() for shop_id in v.split(",") if shop_id.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
