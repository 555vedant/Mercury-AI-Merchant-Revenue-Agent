"""Payment boundary: only policy-approved offers can create payment orders."""
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

import razorpay

from agenticpay.policy_gate import PolicyDecision, PolicyResult

class PaymentNotAllowedError(PermissionError):
    pass

def require_payment_allowed(policy_result: PolicyResult) -> None:
    if policy_result.decision is not PolicyDecision.ALLOW:
        raise PaymentNotAllowedError(f"Payment creation denied: {policy_result.decision.value}. {policy_result.reason}")

def create_razorpay_order(policy_result: PolicyResult, create_order: Callable[..., Any], **order_kwargs: Any) -> Any:
    """Run a caller-supplied Razorpay order creator only after ALLOW."""
    require_payment_allowed(policy_result)
    return create_order(**order_kwargs)


def create_razorpay_test_order(
    policy_result: PolicyResult,
    key_id: str | None = None,
    key_secret: str | None = None,
    receipt: str = "agenticpay-test-order",
) -> dict[str, Any]:
    """Create a Razorpay Test Mode order for an allowed rupee amount."""
    require_payment_allowed(policy_result)
    key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
    key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required.")

    amount_paise = int(
        (Decimal(str(policy_result.transaction_amount)) * Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    if amount_paise <= 0:
        raise ValueError("The agreed amount must be positive.")

    client = razorpay.Client(auth=(key_id, key_secret))
    order = create_razorpay_order(
        policy_result,
        client.order.create,
        amount=amount_paise,
        currency="INR",
        receipt=receipt,
    )
    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "status": order["status"],
    }


def verify_razorpay_payment_signature(
    order_id: str,
    payment_id: str,
    signature: str,
    key_id: str | None = None,
    key_secret: str | None = None,
) -> bool:
    """Verify a Razorpay payment signature; invalid signatures raise an SDK error."""
    key_id = key_id or os.getenv("RAZORPAY_KEY_ID")
    key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required.")
    client = razorpay.Client(auth=(key_id, key_secret))
    client.utility.verify_payment_signature(
        {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }
    )
    return True
