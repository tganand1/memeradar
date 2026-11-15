from __future__ import annotations

import hmac
import hashlib
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.env import ENV

router = APIRouter(prefix="/api/auth")

# In-memory active session tokens
_VALID_TOKENS: dict[str, float] = {}

def generate_session_token() -> str:
    raw = f"{ENV.dashboard_password}-{time.time()}-{hashlib.sha256(os.urandom(16)).hexdigest()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def verify_token(token: str | None) -> bool:
    if not ENV.dashboard_auth_enabled:
        return True
    if not token:
        return False
    expiry = _VALID_TOKENS.get(token)
    if not expiry or time.time() > expiry:
        if token in _VALID_TOKENS:
            del _VALID_TOKENS[token]
        return False
    return True

class LoginBody(BaseModel):
    password: str

@router.get("/status")
async def auth_status(request: Request) -> dict[str, bool]:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else request.query_params.get("token", "")
    authenticated = verify_token(token) if ENV.dashboard_auth_enabled else True
    return {"enabled": ENV.dashboard_auth_enabled, "authenticated": authenticated}

@router.post("/login")
async def login(body: LoginBody) -> dict[str, Any]:
    import os
    if not ENV.dashboard_auth_enabled:
        return {"token": "no-auth-required", "authenticated": True}
    if hmac.compare_digest(body.password, ENV.dashboard_password):
        token = generate_session_token()
        _VALID_TOKENS[token] = time.time() + 7 * 86400  # 7 days
        return {"token": token, "authenticated": True}
    raise HTTPException(status_code=401, detail="Invalid dashboard password")
