"""Deterministic policy gate for negotiated e-commerce offers."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Optional
from agenticpay.commerce import MerchantData
from agenticpay.revenue_engine import RevenueEngine

class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"

@dataclass(frozen=True)
class PolicyContext:
    agreed_price: float
    quantity: int
    category: str
    merchant: MerchantData
    @property
    def transaction_amount(self) -> float:
        return self.agreed_price * self.quantity

MerchantRule = Callable[[PolicyContext], Optional[str]]

@dataclass(frozen=True)
class PolicyConfig:
    maximum_autonomous_amount: float
    minimum_margin_rate: float
    maximum_discount_rate: float
    human_approval_amount: Optional[float] = None
    blocked_categories: frozenset[str] = frozenset()
    allowed_categories: Optional[frozenset[str]] = None
    merchant_rules: tuple[MerchantRule, ...] = ()

@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str
    failed_rules: tuple[str, ...] = ()
    transaction_amount: float = 0.0
    margin_rate: float = 0.0
    @property
    def is_allowed(self) -> bool:
        return self.decision is PolicyDecision.ALLOW
    def to_dict(self) -> dict[str, object]:
        return {"decision": self.decision.value, "reason": self.reason, "failed_rules": list(self.failed_rules), "transaction_amount": self.transaction_amount, "margin_rate": self.margin_rate}

class PolicyGate:
    """Evaluate final offers using deterministic merchant rules only."""
    def __init__(self, config: PolicyConfig):
        self.config = config

    def evaluate(self, context: PolicyContext) -> PolicyResult:
        if context.agreed_price <= 0 or context.quantity <= 0:
            return self._block("Offer must have a positive price and quantity.", ["valid_transaction"])
        failures: list[str] = []
        amount = context.transaction_amount
        category = context.category.lower()
        margin = RevenueEngine(context.merchant).evaluate(context.agreed_price, context.quantity)["margin_rate"]
        discount = max(0.0, (context.merchant.list_price - context.agreed_price) / context.merchant.list_price) if context.merchant.list_price else 0.0
        if amount > self.config.maximum_autonomous_amount:
            failures.append("maximum_autonomous_amount")
        if margin < self.config.minimum_margin_rate:
            failures.append("minimum_merchant_margin")
        if context.merchant.inventory_quantity < context.quantity:
            failures.append("inventory_availability")
        if category in {item.lower() for item in self.config.blocked_categories}:
            failures.append("blocked_category")
        if self.config.allowed_categories and category not in {item.lower() for item in self.config.allowed_categories}:
            failures.append("allowed_category")
        if discount > self.config.maximum_discount_rate:
            failures.append("maximum_discount")
        for rule in self.config.merchant_rules:
            failure = rule(context)
            if failure:
                failures.append(failure)
        if failures:
            return self._block(self._failure_reason(failures), failures, amount, margin)
        if self.config.human_approval_amount is not None and amount > self.config.human_approval_amount:
            return PolicyResult(PolicyDecision.HUMAN_APPROVAL, "Transaction requires human approval due to its value.", transaction_amount=amount, margin_rate=margin)
        return PolicyResult(PolicyDecision.ALLOW, "Offer satisfies autonomous transaction policy.", transaction_amount=amount, margin_rate=margin)

    @staticmethod
    def _failure_reason(failures: list[str]) -> str:
        labels = {"maximum_autonomous_amount": "Transaction exceeds autonomous payment limit.", "minimum_merchant_margin": "Transaction does not meet the minimum merchant margin.", "inventory_availability": "Requested quantity is not available in inventory.", "blocked_category": "Product category is restricted.", "allowed_category": "Product category is not allowed.", "maximum_discount": "Discount exceeds the merchant maximum."}
        return labels.get(failures[0], "A merchant-defined policy rule failed.")

    @staticmethod
    def _block(reason: str, failures: Iterable[str], amount: float = 0.0, margin: float = 0.0) -> PolicyResult:
        return PolicyResult(PolicyDecision.BLOCK, reason, tuple(failures), amount, margin)
