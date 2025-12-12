import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

JWT_SERVICE_URL = os.getenv("JWT_SERVICE_URL", "http://35.196.138.189:8001")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://storage.googleapis.com/lionswap-frontend/index.html")

def get_redirect_uri(request_base_url: str) -> str:
    base = request_base_url.rstrip('/')
    
    if base.startswith('http://') and ('.run.app' in base or os.getenv('K_SERVICE') is not None):
        base = base.replace('http://', 'https://', 1)
    
    return f"{base}/auth/google/callback"

