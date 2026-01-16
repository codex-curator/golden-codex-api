"""Webhook signature verification utilities."""

import hashlib
import hmac
import time


def verify_webhook_signature(
    payload: str,
    signature: str,
    secret: str,
    max_age: int = 300,
) -> bool:
    """
    Verify a webhook signature.

    Args:
        payload: The raw request body as a string.
        signature: The X-GCX-Signature header value.
        secret: Your webhook signing secret.
        max_age: Maximum age in seconds (default 5 minutes).

    Returns:
        True if the signature is valid, False otherwise.

    Example:
        >>> from golden_codex import verify_webhook_signature
        >>>
        >>> @app.route("/webhook", methods=["POST"])
        >>> def handle_webhook():
        ...     payload = request.get_data(as_text=True)
        ...     signature = request.headers.get("X-GCX-Signature", "")
        ...
        ...     if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        ...         return "Invalid signature", 401
        ...
        ...     event = request.json
        ...     # Process the event...
        ...     return "OK", 200
    """
    if not signature:
        return False

    # Parse signature header: t=timestamp,v1=hash
    parts: dict[str, str] = {}
    for part in signature.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            parts[key] = value

    timestamp_str = parts.get("t")
    hash_value = parts.get("v1")

    if not timestamp_str or not hash_value:
        return False

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False

    # Check timestamp is within allowed window
    now = int(time.time())
    if abs(now - timestamp) > max_age:
        return False

    # Compute expected signature
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{payload}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(hash_value, expected_hash)


def generate_webhook_signature(
    payload: str,
    secret: str,
    timestamp: int | None = None,
) -> str:
    """
    Generate a webhook signature (for testing purposes).

    Args:
        payload: The request body to sign.
        secret: The signing secret.
        timestamp: Unix timestamp (default: current time).

    Returns:
        The signature header value.

    Example:
        >>> sig = generate_webhook_signature('{"event":"test"}', "secret123")
        >>> print(sig)  # t=1234567890,v1=abc123...
    """
    if timestamp is None:
        timestamp = int(time.time())

    hash_value = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{payload}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"t={timestamp},v1={hash_value}"
