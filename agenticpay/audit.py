"""Simple in-memory audit trail for policy decisions."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from agenticpay.policy_gate import PolicyResult


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    event: str
    data: dict[str, Any]


class AuditTrail:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def _append(self, event: str, payload: dict[str, Any]) -> AuditEntry:
        payload = dict(payload)
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        entry = AuditEntry(payload["timestamp"], event, payload)
        self.entries.append(entry)
        return entry

    def record_event(
        self,
        event: str,
        *,
        decision: str | None = None,
        status: str | None = None,
        reason: str | None = None,
        product: str | None = None,
        agreed_price: float | None = None,
        attempted_price: float | None = None,
        failed_rule: str | None = None,
        inventory: int | float | None = None,
        margin: float | None = None,
        discount: float | None = None,
        amount: float | None = None,
        timestamp: str | None = None,
        **extra: Any,
    ) -> AuditEntry:
        payload: dict[str, Any] = {
            "decision": decision or status or event,
            "status": status or decision or event,
            "reason": reason or "No specific reason recorded.",
            "product": product,
            "agreed_price": agreed_price,
            "attempted_price": attempted_price,
            "failed_rule": failed_rule,
            "inventory": inventory,
            "margin": margin,
            "discount": discount,
            "amount": amount,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        }
        payload.update(extra)
        return self._append(event, payload)

    def record_negotiation_event(
        self,
        status: str,
        reason: str,
        *,
        product: str | None = None,
        agreed_price: float | None = None,
        attempted_price: float | None = None,
        failed_rule: str | None = None,
        inventory: int | float | None = None,
        margin: float | None = None,
        discount: float | None = None,
        amount: float | None = None,
        **extra: Any,
    ) -> AuditEntry:
        return self.record_event(
            "negotiation_event",
            decision=status,
            status=status,
            reason=reason,
            product=product,
            agreed_price=agreed_price,
            attempted_price=attempted_price,
            failed_rule=failed_rule,
            inventory=inventory,
            margin=margin,
            discount=discount,
            amount=amount,
            **extra,
        )

    def record_policy_decision(
        self,
        result: PolicyResult,
        *,
        product: str | None = None,
        agreed_price: float | None = None,
        attempted_price: float | None = None,
        inventory: int | float | None = None,
        margin: float | None = None,
        discount: float | None = None,
        amount: float | None = None,
        **extra: Any,
    ) -> AuditEntry:
        payload = result.to_dict()
        payload.update(
            {
                "decision": result.decision.value,
                "status": result.decision.value,
                "reason": result.reason,
                "product": product,
                "agreed_price": agreed_price if agreed_price is not None else payload.get("transaction_amount"),
                "attempted_price": attempted_price,
                "failed_rule": result.failed_rules[0] if result.failed_rules else None,
                "failed_rules": list(result.failed_rules),
                "inventory": inventory,
                "margin": margin if margin is not None else result.margin_rate,
                "discount": discount,
                "amount": amount if amount is not None else result.transaction_amount,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        payload.update(extra)
        return self._append("policy_decision", payload)

    def record_payment_event(
        self,
        status: str,
        reason: str,
        *,
        product: str | None = None,
        agreed_price: float | None = None,
        attempted_price: float | None = None,
        amount: float | None = None,
        order_id: str | None = None,
        currency: str | None = None,
        **extra: Any,
    ) -> AuditEntry:
        return self.record_event(
            "payment_event",
            decision=status,
            status=status,
            reason=reason,
            product=product,
            agreed_price=agreed_price,
            attempted_price=attempted_price,
            amount=amount,
            order_id=order_id,
            currency=currency,
            **extra,
        )

    def as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(entry) for entry in self.entries]
