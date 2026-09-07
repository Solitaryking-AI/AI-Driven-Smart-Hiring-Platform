"""
auth.py  —  SmartHire AI
Password hashing (bcrypt via passlib) + JWT creation/verification (python-jose).

Design decisions:
  - ACCESS_TOKEN_EXPIRE_MINUTES = 480  (8 hours) — covers a full work day.
    No refresh-token mechanism for now; if a token expires the user simply
    logs in again.  Streamlit detects expiry via 401 from the backend and
    clears session_state automatically.
  - SECRET_KEY is read from the environment variable SMARTHIRE_SECRET_KEY.
    A hard-coded fallback is provided so the app works out of the box in
    development, but the warning printed to stderr reminds operators to set
    it properly in production.
"""

import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

# ---------------------------------------------------------------------------
# Secret key & algorithm
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.environ.get("SMARTHIRE_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = "smarthire-dev-secret-key-change-in-production-2024"
    warnings.warn(
        "SMARTHIRE_SECRET_KEY environment variable is not set. "
        "Using insecure default key. Set the variable before deploying to production.",
        stacklevel=1,
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8-hour work-day token

# ---------------------------------------------------------------------------
# Password hashing  (direct bcrypt — avoids passlib's 72-byte probe bug)
# ---------------------------------------------------------------------------
import bcrypt as _bcrypt


def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain* text password."""
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT.  *data* should contain at least {"sub": email}.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT.
    Returns the payload dict on success, or None if the token is invalid/expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
