"""Seller negotiation agent with merchant revenue controls and CVO."""

import json
from typing import Any, Dict, List, Optional

from agenticpay.audit import AuditTrail
from agenticpay.agents.base_agent import BaseAgent
from agenticpay.commerce import MerchantData
from agenticpay.models.base_llm import BaseLLM
from agenticpay.revenue_engine import RevenueEngine
from agenticpay.merchant_policy import (
    MerchantPolicy,
    reward_for_episode,
)
from agenticpay.policy_gate import (
    PolicyConfig,
    PolicyContext,
    PolicyGate,
)


class SellerAgent(BaseAgent):

    def __init__(
        self,
        model: BaseLLM,
        name: str = "Seller",
        role_description: str = (
            "an e-commerce seller seeking profitable sales"
        ),
        seller_min_price: Optional[float] = None,
        merchant_data: Optional[MerchantData] = None,
        merchant_policy: Optional[MerchantPolicy] = None,
        policy_gate: Optional[PolicyGate] = None,
        audit_trail: Optional[AuditTrail] = None,
        clv_score: Optional[float] = None,
        cvo_threshold: float = 50.0,
        cvo_max_concession_rate: float = 0.05,
    ):

        super().__init__(
            model,
            role_description,
            name,
        )

        self.seller_min_price = seller_min_price

        self.revenue_engine = (
            RevenueEngine(merchant_data)
            if merchant_data
            else None
        )

        self.last_decision: Dict[str, float] = {}
        self.last_offer: Optional[float] = None

        self.merchant_policy = (
            merchant_policy
            or (
                MerchantPolicy()
                if merchant_data
                else None
            )
        )

        self.policy_gate = (
            policy_gate
            or (
                PolicyGate(
                    PolicyConfig(
                        maximum_autonomous_amount=float("inf"),
                        minimum_margin_rate=(
                            merchant_data.minimum_margin_rate
                            if merchant_data
                            else 0.0
                        ),
                        maximum_discount_rate=1.0,
                        blocked_categories=frozenset(),
                    )
                )
                if merchant_data
                else None
            )
        )

        self.last_action: Optional[str] = None
        self.last_state: Optional[str] = None
        self.learned_at_start = False

        self.audit_trail = audit_trail

        self.clv_score = clv_score
        self.cvo_threshold = cvo_threshold
        self.cvo_max_concession_rate = (
            cvo_max_concession_rate
        )

    # ---------------------------------------------------------
    # AUDIT
    # ---------------------------------------------------------

    def _record_decision(
        self,
        action: str,
        *,
        reason: str,
        offer_price: Optional[float],
        attempted_price: Optional[float],
        failed_rule: Optional[str] = None,
    ) -> None:

        if not self.audit_trail:
            return

        product_info = (
            self.context.get("product_info")
            if isinstance(self.context, dict)
            else None
        )

        product_name = (
            product_info.get("name")
            if isinstance(product_info, dict)
            else None
        )

        inventory = (
            getattr(
                self.revenue_engine.merchant,
                "inventory_quantity",
                None,
            )
            if self.revenue_engine
            else None
        )

        margin = (
            self.revenue_engine.evaluate(
                offer_price
            )["margin_rate"]
            if self.revenue_engine
            and offer_price is not None
            else None
        )

        discount = None

        if (
            self.revenue_engine
            and offer_price is not None
            and self.revenue_engine.merchant.list_price
        ):
            discount = max(
                0.0,
                (
                    self.revenue_engine.merchant.list_price
                    - offer_price
                )
                / self.revenue_engine.merchant.list_price,
            )

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

    # ---------------------------------------------------------
    # MAIN NEGOTIATION
    # ---------------------------------------------------------

    def respond(
        self,
        conversation_history: List[Dict[str, Any]],
        current_state: Dict[str, Any],
    ) -> str:

        if not self.initialized:
            raise RuntimeError(
                "Initialize the seller before negotiating."
            )

        # -----------------------------------------------------
        # ECONOMIC BOUNDARIES
        # -----------------------------------------------------

        floor = (
            self.revenue_engine.minimum_viable_price
            if self.revenue_engine
            else float(
                self.seller_min_price
                if self.seller_min_price is not None
                else self.context["min_price"]
            )
        )

        original_target = (
            self.revenue_engine.target_price
            if self.revenue_engine
            else float(
                self.context.get(
                    "initial_price",
                    floor * 1.25,
                )
            )
        )

        buyer_price = self._latest_buyer_price(
            conversation_history
        )

        previous_seller_price = self._latest_seller_price(
            conversation_history
        )

        buyer_profitability = (
            self.revenue_engine.evaluate(
                buyer_price
            )
            if self.revenue_engine
            and buyer_price is not None
            else None
        )

        buyer_is_safe = (
            buyer_price is not None
            and buyer_price >= floor
            and (
                buyer_profitability is None
                or buyer_profitability["profit"] > 0
            )
        )

        tolerance = 0.01

        matches_previous_seller = (
            buyer_price is not None
            and previous_seller_price is not None
            and buyer_price >= (
                previous_seller_price - tolerance
            )
        )

        buyer_maximum = float(
            self.context.get("max_price")
            or original_target
        )

        current_margin = (
            buyer_profitability["margin_rate"]
            if buyer_profitability
            else 0.0
        )

        self.learned_at_start = (
            self.merchant_policy.has_learning
            if self.merchant_policy
            else False
        )

        round_number = int(
            current_state.get(
                "current_round",
                0,
            )
        )

        # -----------------------------------------------------
        # BUILD BOTH STATES
        # -----------------------------------------------------

        normal_state = None
        cvo_state = None

        if (
            self.merchant_policy
            and self.revenue_engine
        ):

            normal_state = (
                self.merchant_policy.state_key(
                    self.revenue_engine.merchant.sku,
                    self.revenue_engine.merchant.inventory_quantity,
                    buyer_price,
                    buyer_maximum,
                    current_margin,
                    round_number,
                    None,
                )
            )

            if self.clv_score is not None:
                cvo_state = (
                    self.merchant_policy.state_key(
                        self.revenue_engine.merchant.sku,
                        self.revenue_engine.merchant.inventory_quantity,
                        buyer_price,
                        buyer_maximum,
                        current_margin,
                        round_number,
                        self.clv_score,
                    )
                )

        # -----------------------------------------------------
        # NORMAL / CVO-OFF BASELINE ACTION
        # -----------------------------------------------------

        if matches_previous_seller and buyer_is_safe:

            baseline_action = "ACCEPT"

        elif self.merchant_policy and normal_state:

            baseline_action = (
                self.merchant_policy.select_action(
                    normal_state
                )
            )

        else:

            baseline_action = (
                "ACCEPT"
                if (
                    buyer_is_safe
                    and buyer_price is not None
                    and buyer_price >= (
                        original_target - 2.0
                    )
                )
                else "TARGET_COUNTER"
            )

        # -----------------------------------------------------
        # CVO ACTION
        # -----------------------------------------------------

        cvo_enabled = (
            self.clv_score is not None
            and self.clv_score >= self.cvo_threshold
        )

        if cvo_enabled and self.merchant_policy and cvo_state:

            cvo_action = (
                self.merchant_policy.select_action(
                    cvo_state
                )
            )

        else:

            cvo_action = baseline_action

        # -----------------------------------------------------
        # SAFETY RULE:
        #
        # CVO may only make the merchant MORE flexible.
        #
        # ACCEPT
        # SMALL_COUNTER
        # TARGET_COUNTER
        # REJECT
        #
        # Higher index = less customer-friendly.
        # -----------------------------------------------------

        action_rank = {
            "ACCEPT": 0,
            "SMALL_COUNTER": 1,
            "TARGET_COUNTER": 2,
            "REJECT": 3,
        }

        if cvo_enabled:

            selected_action = (
                cvo_action
                if action_rank[cvo_action]
                < action_rank[baseline_action]
                else baseline_action
            )

        else:

            selected_action = baseline_action

        # -----------------------------------------------------
        # CVO TARGET
        # -----------------------------------------------------

        target = original_target
        cvo_target_applied = False

        if cvo_enabled:

            cvo_target = max(
                floor,
                round(
                    original_target
                    * (
                        1.0
                        - self.cvo_max_concession_rate
                    ),
                    2,
                ),
            )

            # CVO target can ONLY be lower than normal target.
            target = min(
                original_target,
                cvo_target,
            )

            cvo_target_applied = (
                target < original_target
            )

        # -----------------------------------------------------
        # CALCULATE PRICE
        # -----------------------------------------------------

        if selected_action == "ACCEPT":

            if buyer_is_safe:
                price = buyer_price
            else:
                selected_action = "TARGET_COUNTER"
                price = self._counteroffer(
                    buyer_price,
                    floor,
                    target,
                )

        elif selected_action == "SMALL_COUNTER":

            if buyer_price is not None:
                price = max(
                    floor,
                    min(
                        target,
                        buyer_price + 2.0,
                    ),
                )
            else:
                price = target

        elif selected_action == "REJECT":

            price = max(
                floor,
                target,
                (
                    buyer_price + 2.0
                    if buyer_price is not None
                    else target
                ),
            )

        else:

            price = self._counteroffer(
                buyer_price,
                floor,
                target,
            )

        price = max(
            floor,
            round(price, 2),
        )

        # -----------------------------------------------------
        # ACCEPT WHEN BUYER MATCHES PREVIOUS SELLER OFFER
        # -----------------------------------------------------

        if (
            buyer_price is not None
            and selected_action != "REJECT"
            and matches_previous_seller
            and buyer_is_safe
        ):

            selected_action = "ACCEPT"
            price = buyer_price

        # -----------------------------------------------------
        # FINAL CVO SAFETY:
        #
        # Compare with the actual non-CVO price.
        #
        # CVO must NEVER make the merchant quote more
        # than the normal strategy would have quoted.
        # -----------------------------------------------------

        baseline_price = self._price_for_action(
            baseline_action,
            buyer_price,
            floor,
            original_target,
            buyer_is_safe,
            matches_previous_seller,
        )

        baseline_price = max(
            floor,
            round(baseline_price, 2),
        )

        if cvo_enabled:

            # CVO can never worsen the customer's offer.
            price = min(
                price,
                baseline_price,
            )

            # If the final price equals the buyer's safe
            # offer, acceptance is valid.
            if (
                buyer_price is not None
                and price == buyer_price
                and buyer_is_safe
                and selected_action != "REJECT"
            ):
                selected_action = "ACCEPT"

        # -----------------------------------------------------
        # FINAL HARD POLICY CHECK
        # -----------------------------------------------------

        if (
            selected_action == "ACCEPT"
            and (
                buyer_price is None
                or not self.is_offer_allowed(price)
            )
        ):

            selected_action = "REJECT"

        if (
            selected_action == "TARGET_COUNTER"
            and not self.is_offer_allowed(price)
        ):

            selected_action = "REJECT"

        if (
            selected_action == "SMALL_COUNTER"
            and not self.is_offer_allowed(price)
        ):

            selected_action = "REJECT"

        # -----------------------------------------------------
        # SAVE LEARNING STATE
        # -----------------------------------------------------

        self.last_state = (
            cvo_state
            if cvo_enabled and cvo_state
            else normal_state
        )

        self.last_action = selected_action

        # -----------------------------------------------------
        # CVO AUDIT TRACE
        # -----------------------------------------------------

        cvo_trace = ""

        if cvo_enabled:

            changes = []

            if cvo_action != baseline_action:
                changes.append(
                    f"Action {baseline_action} → {selected_action}"
                )

            if price != baseline_price:
                changes.append(
                    f"Offer ₹{baseline_price:.2f} → ₹{price:.2f}"
                )

            if cvo_target_applied:
                changes.append(
                    f"Target ₹{original_target:.2f} → ₹{target:.2f}"
                )

            if changes:

                cvo_trace = (
                    " [CVO Trace: "
                    + "; ".join(changes)
                    + "]"
                )

        # -----------------------------------------------------
        # AUDIT REASON
        # -----------------------------------------------------

        reason = (
            "The seller selected a strategy aligned "
            "with merchant guardrails."
        )

        failed_rule = None

        if selected_action == "REJECT":

            reason = (
                "The seller rejected the offer because "
                "it failed merchant policy checks."
            )

        elif selected_action == "ACCEPT":

            reason = (
                "The seller accepted the buyer's offer "
                "because it satisfies policy and "
                "profitability rules."
            )

        elif selected_action in {
            "SMALL_COUNTER",
            "TARGET_COUNTER",
        }:

            reason = (
                "The seller countered with a price that "
                "respects margin and discount guardrails."
            )

        if cvo_trace:
            reason += cvo_trace

        self._record_decision(
            selected_action,
            reason=reason,
            offer_price=price,
            attempted_price=buyer_price,
            failed_rule=failed_rule,
        )

        self.last_offer = price

        self.last_decision = (
            self.revenue_engine.evaluate(price)
            if self.revenue_engine
            else {
                "revenue": price,
                "cost": 0.0,
                "profit": price,
                "margin_rate": 1.0,
            }
        )

        # -----------------------------------------------------
        # GEMINI ONLY GENERATES LANGUAGE
        # -----------------------------------------------------

        prompt = f"""
You are an e-commerce seller.

Product:
{self.context.get("product_info", {})}

Customer CLV:
{self.clv_score}

Conversation:
{self._history_text(conversation_history)}

Selected strategy:
{selected_action}

Valid offer:
₹{price:.2f}

Return JSON only:

{{
  "message": "one concise, polite sentence supporting the selected strategy and offer"
}}

Do not reveal internal costs, margins, Q-values,
CVO thresholds, policy rules, or implementation details.
Do not generate or modify the numeric offer.
"""

        message = self._message(
            self.model.generate(
                prompt,
                temperature=0.0,
                max_tokens=80,
                response_mime_type="application/json",
                response_json_schema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string"
                        }
                    },
                    "required": ["message"],
                },
            )
        )

        return (
            f"{message} "
            f"### SELLER_ACTION({selected_action}) ### "
            f"### SELLER_PRICE(${price:.2f}) ###"
        )

    # ---------------------------------------------------------
    # PRICE CALCULATION
    # ---------------------------------------------------------

    @staticmethod
    def _price_for_action(
        action: str,
        buyer_price: Optional[float],
        floor: float,
        target: float,
        buyer_is_safe: bool,
        matches_previous_seller: bool,
    ) -> float:

        if (
            action == "ACCEPT"
            and buyer_is_safe
            and buyer_price is not None
        ):
            return buyer_price

        if action == "SMALL_COUNTER":

            if buyer_price is not None:
                return max(
                    floor,
                    min(
                        target,
                        buyer_price + 2.0,
                    ),
                )

            return target

        if action == "REJECT":

            return max(
                floor,
                target,
                (
                    buyer_price + 2.0
                    if buyer_price is not None
                    else target
                ),
            )

        return SellerAgent._counteroffer(
            buyer_price,
            floor,
            target,
        )

    # ---------------------------------------------------------
    # POLICY CHECK
    # ---------------------------------------------------------

    def is_offer_allowed(
        self,
        price: float,
    ) -> bool:

        if (
            not self.policy_gate
            or not self.revenue_engine
        ):

            return (
                self.revenue_engine is None
                or self.revenue_engine.evaluate(
                    price
                )["profit"] > 0
            )

        result = self.policy_gate.evaluate(
            PolicyContext(
                agreed_price=price,
                quantity=1,
                category=(
                    self.revenue_engine
                    .merchant
                    .category
                ),
                merchant=(
                    self.revenue_engine
                    .merchant
                ),
            )
        )

        return result.is_allowed

    # ---------------------------------------------------------
    # RL EPISODE
    # ---------------------------------------------------------

    def finish_episode(
        self,
        converted: bool,
        profit: float,
        margin: float,
    ) -> None:

        if (
            not self.merchant_policy
            or not self.last_state
            or not self.last_action
        ):
            return

        reward = reward_for_episode(
            converted,
            profit,
            margin,
            self.last_action == "REJECT",
        )

        self.merchant_policy.update(
            self.last_state,
            self.last_action,
            reward,
        )

        self.merchant_policy.record_episode(
            self.learned_at_start,
            converted,
            profit,
            self.last_offer
            if converted
            else None,
        )

    # ---------------------------------------------------------
    # COUNTER OFFER
    # ---------------------------------------------------------

    @staticmethod
    def _counteroffer(
        buyer_price: Optional[float],
        floor: float,
        target: float,
    ) -> float:

        if buyer_price is None:
            return round(target, 2)

        if buyer_price >= target:
            return round(buyer_price, 2)

        return round(
            max(
                floor,
                buyer_price
                + 0.60 * (target - buyer_price),
            ),
            2,
        )

    # ---------------------------------------------------------
    # MESSAGE
    # ---------------------------------------------------------

    @staticmethod
    def _message(raw: str) -> str:

        try:

            return str(
                json.loads(raw).get("message")
                or (
                    "I can adjust the price while "
                    "keeping the offer sustainable."
                )
            ).strip()

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):

            cleaned = raw.strip()

            return (
                cleaned
                if len(cleaned) >= 12
                else (
                    "I can adjust the price while "
                    "keeping the offer sustainable."
                )
            )

    # ---------------------------------------------------------
    # HISTORY PARSING
    # ---------------------------------------------------------

    @staticmethod
    def _latest_buyer_price(
        history: List[Dict[str, Any]],
    ) -> Optional[float]:

        import re

        for item in reversed(history):

            if item.get("role") != "buyer":
                continue

            match = re.search(
                r"###\s*BUYER_PRICE\(\$?\s*"
                r"([0-9]+(?:\.[0-9]+)?)\s*\)\s*###",
                item.get("content", ""),
                re.IGNORECASE,
            )

            if match:
                return float(match.group(1))

        return None

    @staticmethod
    def _latest_seller_price(
        history: List[Dict[str, Any]],
    ) -> Optional[float]:

        import re

        for item in reversed(history):

            if item.get("role") != "seller":
                continue

            match = re.search(
                r"###\s*SELLER_PRICE\(\$?\s*"
                r"([0-9]+(?:\.[0-9]+)?)\s*\)\s*###",
                item.get("content", ""),
                re.IGNORECASE,
            )

            if match:
                return float(match.group(1))

        return None