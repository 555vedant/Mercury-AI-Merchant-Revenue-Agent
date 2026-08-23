"""Payment boundary: only policy-approved offers can create payment orders."""
from typing import Any, Callable
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
