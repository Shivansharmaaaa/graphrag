"""Authentication, roles and TLP policy (FR11, Section 7.4)."""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import stores
from app.config import settings

# ---------------------------------------------------------------- TLP ordering
TLP_ORDER = ["WHITE", "GREEN", "AMBER", "RED"]
TLP_ALIASES = {"CLEAR": "WHITE", "AMBER+STRICT": "AMBER"}


def norm_tlp(tlp: str | None) -> str:
    t = (tlp or "WHITE").upper().replace("TLP:", "").strip()
    t = TLP_ALIASES.get(t, t)
    return t if t in TLP_ORDER else "AMBER"  # unknown marking → treat conservatively


def tlp_rank(tlp: str | None) -> int:
    return TLP_ORDER.index(norm_tlp(tlp))


def allowed_tlps(clearance: str) -> list[str]:
    """All TLP levels a user with this clearance may read."""
    return TLP_ORDER[: tlp_rank(clearance) + 1]


def can_read(user: dict, tlp: str | None) -> bool:
    return tlp_rank(tlp) <= tlp_rank(user["clearance"])


def max_tlp(tlps) -> str:
    tl = [norm_tlp(t) for t in tlps if t]
    return max(tl, key=tlp_rank) if tl else "WHITE"


# ---------------------------------------------------------------- roles
# analyst : query graph / documents / search / GraphRAG (Section 5.1 primary stakeholder)
# lead    : + publish / revoke blocklist IOCs, ingest reports (CTI lead / detection engineer)
# admin   : + seed, reindex, delete reports, view all audit entries (platform operator / SRE)
ROLE_RANK = {"analyst": 0, "lead": 1, "admin": 2}

DEFAULT_USERS = [
    {"username": "analyst", "password": "analyst123", "role": "analyst", "clearance": "AMBER",
     "display": "SOC Analyst"},
    {"username": "junior", "password": "junior123", "role": "analyst", "clearance": "GREEN",
     "display": "Junior Analyst (GREEN only)"},
    {"username": "lead", "password": "lead123", "role": "lead", "clearance": "RED",
     "display": "CTI Lead / Detection Engineer"},
    {"username": "admin", "password": "admin123", "role": "admin", "clearance": "RED",
     "display": "Platform Operator"},
]


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def ensure_default_users() -> None:
    users = stores.mongo_db().users
    for u in DEFAULT_USERS:
        if not users.find_one({"username": u["username"]}):
            users.insert_one({
                "_id": u["username"], "username": u["username"],
                "password_hash": hash_password(u["password"]),
                "role": u["role"], "clearance": u["clearance"], "display": u["display"],
            })


def authenticate(username: str, password: str) -> dict | None:
    u = stores.mongo_db().users.find_one({"username": username})
    if not u or not verify_password(password, u["password_hash"]):
        return None
    return public_user(u)


def public_user(u: dict) -> dict:
    return {"username": u["username"], "role": u["role"],
            "clearance": u["clearance"], "display": u.get("display", u["username"])}


def create_token(user: dict) -> str:
    now = int(time.time())
    payload = {**user, "sub": user["username"], "iat": now,
               "exp": now + settings.jwt_expiry_minutes * 60}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


_bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    try:
        p = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    return {"username": p["sub"], "role": p["role"], "clearance": p["clearance"],
            "display": p.get("display", p["sub"])}


def require_role(min_role: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if ROLE_RANK.get(user["role"], -1) < ROLE_RANK[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role '{min_role}' or higher")
        return user
    return dep


def consumer_key(x_api_key: str | None = Header(default=None)) -> str:
    """Enforcement consumers (firewall/EDR/SIEM) authenticate with an API key, not a user."""
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.consumer_api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid consumer API key")
    return x_api_key
