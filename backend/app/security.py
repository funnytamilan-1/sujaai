import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"
SECRET_KEY = os.getenv("SECRET_KEY", "")
APP_ENV = os.getenv("APP_ENV", "development")
if APP_ENV == "production" and len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters in production")
if not SECRET_KEY:
    raise RuntimeError("Set SECRET_KEY in the backend environment before starting the API")

bearer = HTTPBearer(auto_error=True)

def verify_admin(email: str, password: str) -> bool:
    expected_email = os.getenv("ADMIN_EMAIL", "")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    return bool(expected_email and expected_password) and hmac.compare_digest(email.lower(), expected_email.lower()) and hmac.compare_digest(password, expected_password)

def issue_token(email: str, role: str = "owner") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": email, "role": role, "iat": now, "exp": now + timedelta(hours=8)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email, role = payload.get("sub"), payload.get("role")
        if not email or role not in {"owner", "admin", "staff"}:
            raise ValueError("Invalid claims")
        return {"email": email, "role": role}
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
