"""FastAPI dashboard backend API — runs alongside the Telegram bot on port 8080."""

import jwt
import time
import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import vpn, adguard
from .config import DASHBOARD_PIN, JWT_SECRET

logger = logging.getLogger(__name__)

app = FastAPI(title="ExpressVPN Gateway API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ─────────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    pin: str


def verify_token(authorization: str = Header(None)) -> dict:
    """Verify JWT bearer token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        return jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


@app.post("/api/auth")
async def auth(req: AuthRequest):
    """Authenticate with a PIN and receive a JWT."""
    if req.pin != DASHBOARD_PIN:
        raise HTTPException(401, "Invalid PIN")
    token = jwt.encode(
        {"exp": time.time() + 86400, "role": "viewer"},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"token": token}


# ── Status ───────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status(user: dict = Depends(verify_token)):
    """Get overall VPN status, IP, and routing mode."""
    status = await vpn.get_status()
    ip_info = await vpn.get_public_ip()
    mode = await vpn.get_current_mode()
    return {"status": status, "ip": ip_info, "mode": mode}


# ── AdGuard ──────────────────────────────────────────────────────────────────

@app.get("/api/adguard")
async def get_adguard(user: dict = Depends(verify_token)):
    """Get AdGuard Home status."""
    status = await adguard.get_status()
    return {"status": status}


@app.post("/api/adguard/toggle")
async def toggle_adguard(user: dict = Depends(verify_token)):
    """Toggle AdGuard protection on/off."""
    status_data = await adguard._request("GET", "/status")
    current = status_data.get("protection_enabled", True) if isinstance(status_data, dict) else True
    result = await adguard.toggle_protection(not current)
    return {"result": result, "enabled": not current}


# ── Mode ─────────────────────────────────────────────────────────────────────

@app.get("/api/mode")
async def get_mode(user: dict = Depends(verify_token)):
    """Get current routing mode."""
    mode = await vpn.get_current_mode()
    return {"mode": mode}
