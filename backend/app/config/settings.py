from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union, Any, Optional
import os

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # CORS origins
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    CORS_ORIGIN_REGEX: Optional[str] = None
    
    SUPABASE_URL: str = "your-supabase-url-here"
    SUPABASE_KEY: str = "your-supabase-anon-key-here"
    
    GEMINI_API_KEY: str = "your-gemini-api-key-here"
    SARVAM_API_KEY: str = ""
    
    # Providers
    STT_PROVIDER: str = "sarvam"
    EXTRACTION_PROVIDER: str = "gemini"
    ENABLE_OLLAMA: bool = False
    # Enable fallback Layer 2 LLM Normalizer for messy hinglish
    ENABLE_LLM_FALLBACK: bool = True
    # Enable One-Call LLM Transliteration for Devanagari ASR transcripts
    ENABLE_LLM_TRANSLITERATION: bool = False

    # Security: Require JWT Auth for backend routes
    REQUIRE_AUTH: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
