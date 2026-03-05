"""Token/credit management service."""

from datetime import datetime

from fastapi import HTTPException, status
from google.cloud import firestore

from ..config import get_settings
from ..models import Operation, OperationOptions
from .auth import get_db


def calculate_cost(
    operations: list[Operation],
    options: OperationOptions | None = None,
) -> tuple[int, dict[str, dict]]:
    """
    Calculate the total cost and breakdown for operations.

    Returns:
        Tuple of (total_cost, breakdown_dict)
    """
    settings = get_settings()
    options = options or OperationOptions()
    total = 0
    breakdown: dict[str, dict] = {}

    if Operation.NOVA in operations:
        nova_opts = options.nova
        tier = nova_opts.tier if nova_opts else "standard"
        cost = settings.cost_nova_full if tier == "full_gcx" else settings.cost_nova_standard
        total += cost
        breakdown["nova"] = {"cost": cost, "tier": tier}

    if Operation.FLUX in operations:
        flux_opts = options.flux
        model = flux_opts.model if flux_opts else "4x"
        cost = settings.cost_flux_4x if model in ("4x", "anime", "photo") else settings.cost_flux_2x
        total += cost
        breakdown["flux"] = {"cost": cost, "model": model}

    if Operation.ATLAS in operations:
        cost = settings.cost_atlas
        total += cost
        breakdown["atlas"] = {"cost": cost}

    return total, breakdown


def check_balance(user_id: str, required: int) -> tuple[bool, int]:
    """
    Check if user has sufficient balance.

    Returns:
        Tuple of (has_sufficient, current_balance)
    """
    db = get_db()
    user_doc = db.collection("users").document(user_id).get()

    if not user_doc.exists:
        return False, 0

    user_data = user_doc.to_dict()

    # credits_available is the primary balance (set by website/Stripe)
    # tokens.balance is the API-tracked balance (legacy)
    # Use whichever is larger — they represent the same pool
    credits_available = user_data.get("credits_available", 0)
    tokens_balance = user_data.get("tokens", {}).get("balance", 0)
    balance = max(int(credits_available), int(tokens_balance))

    return balance >= required, int(balance)


def deduct_tokens(
    user_id: str,
    amount: int,
    reason: str,
    job_id: str,
) -> int:
    """
    Atomically deduct tokens from user's balance.

    Args:
        user_id: User ID
        amount: Amount to deduct
        reason: Reason for deduction
        job_id: Associated job ID

    Returns:
        New balance after deduction

    Raises:
        HTTPException: If insufficient balance
    """
    db = get_db()

    @firestore.transactional
    def deduct_in_transaction(transaction, user_ref):
        user_snapshot = user_ref.get(transaction=transaction)

        if not user_snapshot.exists:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": {
                        "code": "user_not_found",
                        "message": "User account not found",
                    }
                },
            )

        user_data = user_snapshot.to_dict()

        # Use credits_available as primary, tokens.balance as fallback
        credits_available = int(user_data.get("credits_available", 0))
        tokens_balance = int(user_data.get("tokens", {}).get("balance", 0))
        current_balance = max(credits_available, tokens_balance)

        if current_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": {
                        "code": "insufficient_credits",
                        "message": f"Account has {current_balance} GCX but operation requires {amount} GCX",
                        "balance": current_balance,
                        "required": amount,
                    }
                },
            )

        new_balance = current_balance - amount

        # Update both balance fields to keep them in sync
        transaction.update(user_ref, {
            "credits_available": new_balance,
            "tokens.balance": new_balance,
            "tokens.totalSpent": firestore.Increment(amount),
        })

        # Create transaction record
        tx_ref = user_ref.collection("tokenTransactions").document()
        transaction.set(tx_ref, {
            "type": "deduction",
            "amount": amount,
            "reason": reason,
            "job_id": job_id,
            "balance_after": new_balance,
            "created_at": firestore.SERVER_TIMESTAMP,
            "source": "api",
        })

        return new_balance

    user_ref = db.collection("users").document(user_id)
    transaction = db.transaction()
    return deduct_in_transaction(transaction, user_ref)


def refund_tokens(
    user_id: str,
    amount: int,
    reason: str,
    job_id: str,
) -> int:
    """
    Refund tokens to user's balance (e.g., on job failure).

    Returns:
        New balance after refund
    """
    db = get_db()

    @firestore.transactional
    def refund_in_transaction(transaction, user_ref):
        user_snapshot = user_ref.get(transaction=transaction)

        if not user_snapshot.exists:
            return 0

        user_data = user_snapshot.to_dict()
        credits_available = int(user_data.get("credits_available", 0))
        tokens_balance = int(user_data.get("tokens", {}).get("balance", 0))
        current_balance = max(credits_available, tokens_balance)

        new_balance = current_balance + amount

        # Update both balance fields to keep them in sync
        transaction.update(user_ref, {
            "credits_available": new_balance,
            "tokens.balance": new_balance,
            "tokens.totalSpent": firestore.Increment(-amount),
        })

        # Create transaction record
        tx_ref = user_ref.collection("tokenTransactions").document()
        transaction.set(tx_ref, {
            "type": "refund",
            "amount": amount,
            "reason": reason,
            "job_id": job_id,
            "balance_after": new_balance,
            "created_at": firestore.SERVER_TIMESTAMP,
            "source": "api",
        })

        return new_balance

    user_ref = db.collection("users").document(user_id)
    transaction = db.transaction()
    return refund_in_transaction(transaction, user_ref)
