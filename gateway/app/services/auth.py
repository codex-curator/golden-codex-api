"""Authentication and authorization service."""

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from google.cloud import firestore

from ..config import get_settings
from ..models import SubscriptionTier


@dataclass
class AuthContext:
    """Authenticated request context."""

    user_id: str
    key_id: str
    tier: SubscriptionTier
    balance: int
    is_test_mode: bool
    permissions: list[str]


# Firestore client (lazy initialized)
_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    """Get Firestore client instance."""
    global _db
    if _db is None:
        settings = get_settings()
        _db = firestore.Client(
            project=settings.gcp_project,
            database=settings.firestore_database,
        )
    return _db


async def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    """
    Verify API key and return auth context.

    Extracts API key from Authorization header, validates it against
    Firestore, and returns the authenticated user context.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "missing_api_key",
                    "message": "Authorization header required. Use: Bearer gcx_live_xxx",
                }
            },
        )

    # Extract bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_auth_format",
                    "message": "Authorization header must use Bearer scheme",
                }
            },
        )

    api_key = authorization[7:]  # Remove "Bearer "

    # Validate key format
    if not api_key.startswith(("gcx_live_", "gcx_test_")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_api_key_format",
                    "message": "API key must start with gcx_live_ or gcx_test_",
                }
            },
        )

    is_test_mode = api_key.startswith("gcx_test_")

    # Hash the key for lookup
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Look up key in Firestore
    db = get_db()
    key_doc = db.collection("api_keys").document(key_hash).get()

    if not key_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_api_key",
                    "message": "API key is invalid or has been revoked",
                }
            },
        )

    key_data = key_doc.to_dict()

    # Check if key is active
    if not key_data.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "api_key_revoked",
                    "message": "This API key has been revoked",
                }
            },
        )

    # Update last_used_at (fire and forget)
    key_doc.reference.update({"last_used_at": firestore.SERVER_TIMESTAMP})

    # Get user data
    user_id = key_data["user_id"]
    user_doc = db.collection("users").document(user_id).get()

    if not user_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "user_not_found",
                    "message": "User account associated with this key no longer exists",
                }
            },
        )

    user_data = user_doc.to_dict()

    # Extract user info
    tier_str = user_data.get("subscriptionTier", "FREE_TRIAL")
    try:
        tier = SubscriptionTier(tier_str)
    except ValueError:
        tier = SubscriptionTier.FREE_TRIAL

    # Get balance from tokens.balance or credits_available
    tokens = user_data.get("tokens", {})
    balance = tokens.get("balance", 0)
    if balance == 0:
        balance = user_data.get("credits_available", 0)

    return AuthContext(
        user_id=user_id,
        key_id=key_hash[:12],  # Short ID for logging
        tier=tier,
        balance=int(balance),
        is_test_mode=is_test_mode,
        permissions=key_data.get("permissions", ["jobs:create", "jobs:read"]),
    )


def generate_api_key(environment: str = "live") -> tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_hash)
    """
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(36))
    full_key = f"gcx_{environment}_{random_part}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_hash


def create_api_key_for_user(
    user_id: str,
    name: str,
    environment: str = "live",
) -> dict:
    """
    Create and store a new API key for a user.

    Args:
        user_id: Firebase user ID
        name: Human-readable key name
        environment: "live" or "test"

    Returns:
        Dict with api_key (shown once!), key_id, name, created_at
    """
    full_key, key_hash = generate_api_key(environment)

    db = get_db()
    db.collection("api_keys").document(key_hash).set({
        "user_id": user_id,
        "name": name,
        "prefix": f"gcx_{environment}",
        "key_hint": f"gcx_{environment}_...{full_key[-4:]}",
        "active": True,
        "permissions": ["jobs:create", "jobs:read", "account:read", "webhooks:manage"],
        "created_at": firestore.SERVER_TIMESTAMP,
        "last_used_at": None,
    })

    return {
        "api_key": full_key,  # Only time this is returned
        "key_id": key_hash[:12],
        "name": name,
        "created_at": datetime.utcnow().isoformat(),
    }


# Dependency for routes that require authentication
Auth = Annotated[AuthContext, Depends(verify_api_key)]
