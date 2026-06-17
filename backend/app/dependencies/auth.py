from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config.settings import settings
from app.services.supabase import supabase_client
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Using HTTPBearer for token extraction from headers
security = HTTPBearer(auto_error=False)

async def get_current_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    """
    Dependency to extract and verify the Supabase JWT.
    Returns the user_id if REQUIRE_AUTH is true and token is valid.
    Returns None if REQUIRE_AUTH is false.
    Raises 401 if REQUIRE_AUTH is true and token is missing or invalid.
    """
    if not settings.REQUIRE_AUTH:
        return None
        
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not supabase_client:
        logger.error("REQUIRE_AUTH is true but Supabase client is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase is not configured on the server."
        )

    try:
        # Supabase auth.get_user verifies the JWT automatically
        response = supabase_client.auth.get_user(credentials.credentials)
        if not response or not response.user:
            raise ValueError("Invalid user token")
        return response.user.id
    except Exception as e:
        logger.error(f"JWT Verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )
