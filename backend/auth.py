# backend/auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "240"))
JWT_ALG = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(tech_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": tech_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Dict:
    token = creds.credentials
    payload = decode_token(token)
    return {"tech_id": payload.get("sub"), "role": payload.get("role")}


def require_role(required: str):
    def _dep(user: Dict = Depends(get_current_user)) -> Dict:
        if user.get("role") != required:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep