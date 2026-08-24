"""Seller negotiation agent with merchant revenue controls."""
import json
from typing import Any, Dict, List, Optional

from agenticpay.audit import AuditTrail
from agenticpay.agents.base_agent import BaseAgent
from agenticpay.commerce import MerchantData
from agenticpay.models.base_llm import BaseLLM
from agenticpay.revenue_engine import RevenueEngine
from agenticpay.merchant_policy import MerchantPolicy, reward_for_episode
from agenticpay.policy_gate import PolicyConfig, PolicyContext, PolicyGate

class SellerAgent(BaseAgent):
    def __init__(self, model: BaseLLM, name: str = "Seller", role_description: str = "an e-commerce seller seeking profitable sales", seller_min_price: Optional[float] = None, merchant_data: Optional[MerchantData] = None, merchant_policy: Optional[MerchantPolicy] = None, policy_gate: Optional[PolicyGate] = None, audit_trail: Optional[AuditTrail] = None, clv_score: Optional[float] = None, cvo_threshold: float = 50.0, cvo_max_concession_rate: float = 0.05):
        super().__init__(model, role_description, name)
        self.seller_min_price = seller_min_price
        self.revenue_engine = RevenueEngine(merchant_data) if merchant_data else None
        self.last_decision: Dict[str, float] = {}
        self.last_offer: Optional[float] = None
        self.merchant_policy = merchant_policy or (MerchantPolicy() if merchant_data else None)
        self.policy_gate = policy_gate or (PolicyGate(PolicyConfig(maximum_autonomous_amount=float("inf"), minimum_margin_rate=merchant_data.minimum_margin_rate if merchant_data else 0.0, maximum_discount_rate=1.0, blocked_categories=frozenset())) if merchant_data else None)
        self.last_action: Optional[str] = None
        self.last_state: Optional[str] = None
        self.learned_at_start = False
        self.audit_trail = audit_trail
        self.clv_score = clv_score
        self.cvo_threshold = cvo_threshold
        self.cvo_max_concession_rate = cvo_max_concession_rate

    def _record_decision(self, action: str, *, reason: str, offer_price: Optional[float], attempted_price: Optional[float], failed_rule: Optional[str] = None) -> None:
        if not self.audit_trail:
            return
        product_info = self.context.get("product_info") if isinstance(self.context, dict) else None
        product_name = product_info.get("name") if isinstance(product_info, dict) else None
        inventory = getattr(self.revenue_engine.merchant, "inventory_quantity", None) if self.revenue_engine else None
        margin = self.revenue_engine.evaluate(offer_price)["margin_rate"] if self.revenue_engine and offer_price is not None else None
        discount = None
        if self.revenue_engine and offer_price is not None and self.revenue_engine.merchant.list_price:
            discount = max(0.0, (self.revenue_engine.merchant.list_price - offer_price) / self.revenue_engine.merchant.list_price)
        self.audit_trail.record_negotiation_event(
            status=action,
            reason=reason,
            product=product_name,
            agreed_price=offer_price,
            attempted_price=attempted_price,
            failed_rule=failed_rule,
            inventory=inventory,
            margin=margin,
            discount=discount,
            amount=offer_price,
        )

    def respond(self, conversation_history: List[Dict[str, Any]], current_state: Dict[str, Any]) -> str:
        if not self.initialized:
            raise RuntimeError("Initialize the seller before negotiating.")
        floor = self.revenue_engine.minimum_viable_price if self.revenue_engine else float(self.seller_min_price if self.seller_min_price is not None else self.context["min_price"])
        original_target = self.revenue_engine.target_price if self.revenue_engine else float(self.context.get("initial_price", floor * 1.25))
        
        target = original_target
        cvo_concession_applied = False
        if self.clv_score is not None and self.clv_score >= self.cvo_threshold:
            target = max(floor, original_target * (1.0 - self.cvo_max_concession_rate))
            if target < original_target:
                cvo_concession_applied = True

        buyer_price = self._latest_buyer_price(conversation_history)
        previous_seller_price = self._latest_seller_price(conversation_history)
        buyer_profitability = self.revenue_engine.evaluate(buyer_price) if self.revenue_engine and buyer_price is not None else None
        buyer_is_safe = buyer_price is not None and buyer_price >= floor and (buyer_profitability is None or buyer_profitability["profit"] > 0)
        
        tolerance = 0.01
        repeated_offer = buyer_price is not None and previous_seller_price is not None and abs(buyer_price - previous_seller_price) <= tolerance
        matches_previous_seller = buyer_price is not None and previous_seller_price is not None and (buyer_price >= previous_seller_price - tolerance)

        near_target = buyer_price is not None and buyer_price >= target - 2.0
        buyer_maximum = float(self.context.get("max_price") or target)
        current_margin = buyer_profitability["margin_rate"] if buyer_profitability else 0.0
        self.learned_at_start = self.merchant_policy.has_learning if self.merchant_policy else False
        
        state = None
        if self.merchant_policy and self.revenue_engine:
            state = self.merchant_policy.state_key(self.revenue_engine.merchant.sku, self.revenue_engine.merchant.inventory_quantity, buyer_price, buyer_maximum, current_margin, int(current_state.get("current_round", 0)), self.clv_score)
        
        # Determine the action without CVO for trace comparison
        no_cvo_state = None
        no_cvo_action = "TARGET_COUNTER"
        if self.merchant_policy and self.revenue_engine:
            no_cvo_state = self.merchant_policy.state_key(self.revenue_engine.merchant.sku, self.revenue_engine.merchant.inventory_quantity, buyer_price, buyer_maximum, current_margin, int(current_state.get("current_round", 0)), None)
            if matches_previous_seller and buyer_is_safe:
                no_cvo_action = "ACCEPT"
            else:
                no_cvo_action = self.merchant_policy.select_action(no_cvo_state)
        else:
            no_cvo_action = "ACCEPT" if buyer_is_safe and (matches_previous_seller or (buyer_price is not None and buyer_price >= original_target - 2.0)) else "TARGET_COUNTER"

        # Actual action selection (using CVO-enabled state if CVO is ON)
        if matches_previous_seller and buyer_is_safe:
            self.last_action = "ACCEPT"
            self.last_state = state
        elif self.merchant_policy and self.revenue_engine:
            self.last_state = state
            self.last_action = self.merchant_policy.select_action(self.last_state)
        else:
            self.last_action = "ACCEPT" if buyer_is_safe and (matches_previous_seller or (buyer_price is not None and buyer_price >= target - 2.0)) else "TARGET_COUNTER"
        if self.last_action == "ACCEPT" and buyer_is_safe:
            price = buyer_price
        elif self.last_action == "ACCEPT":
            self.last_action = "TARGET_COUNTER"
            price = self._counteroffer(buyer_price, floor, target)
        elif self.last_action == "SMALL_COUNTER" and buyer_price is not None:
            price = max(floor, min(target, buyer_price + 2.0))
        elif self.last_action == "REJECT":
            price = max(floor, target, (buyer_price + 2.0) if buyer_price is not None else target)
        else:
            price = self._counteroffer(buyer_price, floor, target)
        price = max(floor, round(price, 2))
        
        # Seller tolerance acceptance (matches current/previous offer within 0.01 tolerance)
        if buyer_price is not None and self.last_action != "REJECT" and matches_previous_seller and buyer_is_safe:
            self.last_action = "ACCEPT"
            price = buyer_price

        # Explicit constraint check: never accept if the offer is not allowed
        if self.last_action == "ACCEPT" and (buyer_price is None or not self.is_offer_allowed(price)):
            self.last_action = "REJECT" if (price is not None and not self.is_offer_allowed(price)) else "TARGET_COUNTER"
        if self.last_action == "TARGET_COUNTER" and not self.is_offer_allowed(price):
            self.last_action = "REJECT"
            
        # Calculate CVO trace details: did CVO change the outcome?
        cvo_trace = ""
        if self.clv_score is not None:
            # Calculate price without CVO for trace comparison
            if no_cvo_action == "ACCEPT" and buyer_is_safe:
                no_cvo_price = buyer_price
            elif no_cvo_action == "ACCEPT":
                no_cvo_price = self._counteroffer(buyer_price, floor, original_target)
            elif no_cvo_action == "SMALL_COUNTER" and buyer_price is not None:
                no_cvo_price = max(floor, min(original_target, buyer_price + 2.0))
            elif no_cvo_action == "REJECT":
                no_cvo_price = max(floor, original_target, (buyer_price + 2.0) if buyer_price is not None else original_target)
            else:
                no_cvo_price = self._counteroffer(buyer_price, floor, original_target)
            no_cvo_price = max(floor, round(no_cvo_price, 2))

            if no_cvo_action == "ACCEPT" and (buyer_price is None or not self.is_offer_allowed(no_cvo_price)):
                no_cvo_action = "REJECT" if (no_cvo_price is not None and not self.is_offer_allowed(no_cvo_price)) else "TARGET_COUNTER"
            if no_cvo_action == "TARGET_COUNTER" and not self.is_offer_allowed(no_cvo_price):
                no_cvo_action = "REJECT"

            if no_cvo_action != self.last_action or no_cvo_price != price:
                cvo_trace = f" [CVO Trace: Action changed from {no_cvo_action} to {self.last_action}, Offer changed from ₹{no_cvo_price:.2f} to ₹{price:.2f}]"
        reason = "The seller chose a pricing strategy aligned with merchant guardrails."
        failed_rule = None
        if self.last_action == "REJECT":
            reason = "The seller rejected the offer because it failed merchant policy checks."
            if self.policy_gate and self.revenue_engine:
                policy_result = self.policy_gate.evaluate(PolicyContext(agreed_price=price, quantity=1, category=self.revenue_engine.merchant.category, merchant=self.revenue_engine.merchant))
                if not policy_result.is_allowed:
                    reason = policy_result.reason
                    failed_rule = policy_result.failed_rules[0] if policy_result.failed_rules else None
        elif self.last_action == "ACCEPT":
            reason = "The seller accepted the buyer's offer because it satisfies policy and profitability rules."
        elif self.last_action in {"SMALL_COUNTER", "TARGET_COUNTER"}:
            reason = "The seller countered with a price that respects margin and discount guardrails."
        
        if cvo_trace:
            reason += cvo_trace

        self._record_decision(self.last_action, reason=reason, offer_price=price, attempted_price=buyer_price, failed_rule=failed_rule)
        self.last_offer = price
        self.last_decision = self.revenue_engine.evaluate(price) if self.revenue_engine else {"revenue": price, "cost": 0.0, "profit": price, "margin_rate": 1.0}
        prompt = f"""You are an e-commerce seller. Product: {self.context.get('product_info', {})}. Customer CLV Score: {self.clv_score}. Conversation: {self._history_text(conversation_history)}. Your selected strategy is {self.last_action} and your valid offer is ₹{price:.2f}. Return JSON only: {{"message":"one concise, polite sentence supporting this strategy and offer"}}. Do not reveal internal costs, margin rules, or use price tags."""
        message = self._message(self.model.generate(prompt, temperature=0.0, max_tokens=80, response_mime_type="application/json", response_json_schema={"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}))
        return f"{message} ### SELLER_ACTION({self.last_action}) ### ### SELLER_PRICE(${price:.2f}) ###"

    def is_offer_allowed(self, price: float) -> bool:
        if not self.policy_gate or not self.revenue_engine:
            return self.revenue_engine is None or self.revenue_engine.evaluate(price)["profit"] > 0
        result = self.policy_gate.evaluate(PolicyContext(agreed_price=price, quantity=1, category=self.revenue_engine.merchant.category, merchant=self.revenue_engine.merchant))
        return result.is_allowed

    def finish_episode(self, converted: bool, profit: float, margin: float) -> None:
        if not self.merchant_policy or not self.last_state or not self.last_action:
            return
        reward = reward_for_episode(converted, profit, margin, self.last_action == "REJECT")
        self.merchant_policy.update(self.last_state, self.last_action, reward)
        self.merchant_policy.record_episode(self.learned_at_start, converted, profit, self.last_offer if converted else None)

    @staticmethod
    def _counteroffer(buyer_price: Optional[float], floor: float, target: float) -> float:
        if buyer_price is None:
            return round(target, 2)
        if buyer_price >= target:
            return round(buyer_price, 2)
        return round(max(floor, buyer_price + 0.60 * (target - buyer_price)), 2)

    @staticmethod
    def _message(raw: str) -> str:
        try:
            return str(json.loads(raw).get("message") or "I can adjust the price while keeping the offer sustainable.").strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            return raw.strip() if len(raw.strip()) >= 12 else "I can adjust the price while keeping the offer sustainable."

    @staticmethod
    def _latest_buyer_price(history: List[Dict[str, Any]]) -> Optional[float]:
        import re
        for item in reversed(history):
            if item.get("role") != "buyer":
                continue
            match = re.search(r"###\s*BUYER_PRICE\(\$?\s*([0-9]+(?:\.[0-9]+)?)\s*\)\s*###", item.get("content", ""), re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def _latest_seller_price(history: List[Dict[str, Any]]) -> Optional[float]:
        import re
        for item in reversed(history):
            if item.get("role") != "seller":
                continue
            match = re.search(r"###\s*SELLER_PRICE\(\$?\s*([0-9]+(?:\.[0-9]+)?)\s*\)\s*###", item.get("content", ""), re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None


