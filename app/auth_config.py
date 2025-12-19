import os
from dotenv import load_dotenv

load_dotenv()

# Google OAuth2 configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# JWT service URL (other microservice)
# Base URL for JWT service (e.g., http://35.196.138.189:8001)
JWT_SERVICE_URL = os.getenv("JWT_SERVICE_URL", "http://35.196.138.189:8001")

# Frontend URL for OAuth redirect
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://storage.googleapis.com/lionswap-frontend/index.html#")

# OAuth2 redirect URI (automatically set based on environment)
def get_redirect_uri(request_base_url: str) -> str:
    """Dynamically generate redirect URI"""
    base = request_base_url.rstrip('/')
    
    # Force HTTPS for Cloud Run (production)
    # Cloud Run always uses HTTPS, but request.base_url might return http
    if base.startswith('http://') and ('.run.app' in base or os.getenv('K_SERVICE') is not None):
        base = base.replace('http://', 'https://', 1)
    
    return f"{base}/auth/google/callback"