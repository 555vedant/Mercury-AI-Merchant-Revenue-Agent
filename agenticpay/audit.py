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

    def record_policy_decision(self, result: PolicyResult) -> AuditEntry:
        entry = AuditEntry(datetime.now(timezone.utc).isoformat(), "policy_decision", result.to_dict())
        self.entries.append(entry)
        return entry

    def as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(entry) for entry in self.entries]
