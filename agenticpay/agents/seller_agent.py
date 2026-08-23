"""Seller negotiation agent with merchant revenue controls."""
import json
from typing import Any, Dict, List, Optional
from agenticpay.agents.base_agent import BaseAgent
from agenticpay.commerce import MerchantData
from agenticpay.models.base_llm import BaseLLM
from agenticpay.revenue_engine import RevenueEngine

class SellerAgent(BaseAgent):
    def __init__(self, model: BaseLLM, name: str = "Seller", role_description: str = "an e-commerce seller seeking profitable sales", seller_min_price: Optional[float] = None, merchant_data: Optional[MerchantData] = None):
        super().__init__(model, role_description, name)
        self.seller_min_price = seller_min_price
        self.revenue_engine = RevenueEngine(merchant_data) if merchant_data else None
        self.last_decision: Dict[str, float] = {}
        self.last_offer: Optional[float] = None

    def respond(self, conversation_history: List[Dict[str, Any]], current_state: Dict[str, Any]) -> str:
        if not self.initialized:
            raise RuntimeError("Initialize the seller before negotiating.")
        floor = self.revenue_engine.minimum_viable_price if self.revenue_engine else float(self.seller_min_price if self.seller_min_price is not None else self.context["min_price"])
        target = self.revenue_engine.target_price if self.revenue_engine else float(self.context.get("initial_price", floor * 1.25))
        buyer_price = self._latest_buyer_price(conversation_history)
        buyer_profitability = self.revenue_engine.evaluate(buyer_price) if self.revenue_engine and buyer_price is not None else None
        buyer_is_safe = buyer_price is not None and buyer_price >= floor and (buyer_profitability is None or buyer_profitability["profit"] > 0)
        repeated_offer = buyer_price is not None and self.last_offer is not None and abs(buyer_price - self.last_offer) < 0.01
        near_target = buyer_price is not None and buyer_price >= target - 2.0
        price = buyer_price if buyer_is_safe and (repeated_offer or buyer_price >= target or near_target) else self._counteroffer(buyer_price, floor, target)
        self.last_offer = price
        self.last_decision = self.revenue_engine.evaluate(price) if self.revenue_engine else {"revenue": price, "cost": 0.0, "profit": price, "margin_rate": 1.0}
        prompt = f"""You are an e-commerce seller. Product: {self.context.get('product_info', {})}. Conversation: {self._history_text(conversation_history)}. Your revenue-aware counteroffer is ${price:.2f}. Return JSON only: {{"message":"one concise, polite sentence supporting this offer"}}. Do not reveal internal costs, margin rules, or use price tags."""
        message = self._message(self.model.generate(prompt, temperature=0.0, max_tokens=80, response_mime_type="application/json", response_json_schema={"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}))
        return f"{message} ### SELLER_PRICE(${price:.2f}) ###"

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
            match = re.search(r"BUYER_PRICE\(\$?\s*([0-9]+(?:\.[0-9]+)?)", item.get("content", ""), re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None


