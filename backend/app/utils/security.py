import hmac
import hashlib
import base64
from app.config.settings import settings

def generate_deterministic_bill_token(order_id: str, shop_id: str) -> str:
    """
    Generates a deterministic raw token for an order bill link using HMAC SHA-256.
    """
    message = f"bill:{order_id}:{shop_id}".encode('utf-8')
    secret = settings.BILL_LINK_SIGNING_SECRET.encode('utf-8')
    
    mac = hmac.new(secret, message, hashlib.sha256)
    # Use urlsafe base64 and strip padding for a clean URL token
    return base64.urlsafe_b64encode(mac.digest()).decode('utf-8').rstrip('=')

def hash_token(token: str) -> str:
    """
    Hashes a token using SHA-256 for secure database storage.
    """
    return hashlib.sha256(token.encode()).hexdigest()
