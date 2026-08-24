"""Buyer negotiation agent."""
import json
from typing import Any, Dict, List, Optional
from agenticpay.agents.base_agent import BaseAgent
from agenticpay.models.base_llm import BaseLLM

class BuyerAgent(BaseAgent):
    def __init__(self, model: BaseLLM, name: str = "Buyer", role_description: str = "a buyer seeking a fair deal", buyer_max_price: Optional[float] = None):
        super().__init__(model, role_description, name)
        self.buyer_max_price = buyer_max_price

    def respond(self, conversation_history: List[Dict[str, Any]], current_state: Dict[str, Any]) -> str:
        if not self.initialized:
            raise RuntimeError("Initialize the buyer before negotiating.")
        maximum = float(self.buyer_max_price if self.buyer_max_price is not None else self.context["max_price"])
        price = self._next_offer(conversation_history, maximum)
        prompt = f"""You are a buyer negotiating an e-commerce purchase. Product: {self.context.get('product_info', {})}. Conversation: {self._history_text(conversation_history)}. Your next offer is ₹{price:.2f}. Return JSON only: {{"message":"one concise, polite sentence supporting this offer"}}. Do not mention confidential limits or use price tags."""
        message = self._message(self.model.generate(prompt, temperature=0.0, max_tokens=80, response_mime_type="application/json", response_json_schema={"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}))
        return f"{message} ### BUYER_PRICE(${price:.2f}) ###"

    def _next_offer(self, history: List[Dict[str, Any]], maximum: float) -> float:
        previous_buyer = self._latest_price(history, "buyer")
        seller_price = self._latest_price(history, "seller")
        if previous_buyer is None:
            return round(maximum * 0.72, 2)
        if seller_price is None:
            return previous_buyer

        if seller_price <= previous_buyer:
            return round(seller_price, 2)

        import re
        buyer_offer_count = sum(
            1 for msg in history 
            if msg.get("role") == "buyer" and re.search(r"BUYER_PRICE\(\$?\s*[0-9]+", msg.get("content", ""), re.IGNORECASE)
        )

        if seller_price <= maximum:
            if seller_price <= previous_buyer * 1.05 or buyer_offer_count >= 3:
                return round(seller_price, 2)
            counter = previous_buyer + 0.50 * (seller_price - previous_buyer)
            return round(min(maximum, counter), 2)

        counter = previous_buyer + 0.40 * (seller_price - previous_buyer)
        return round(min(maximum, counter), 2)

    @staticmethod
    def _message(raw: str) -> str:
        try:
            return str(json.loads(raw).get("message") or "I can improve my offer slightly.").strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            return raw.strip() if len(raw.strip()) >= 12 else "I can improve my offer slightly."

    @staticmethod
    def _latest_price(history: List[Dict[str, Any]], role: str) -> Optional[float]:
        import re
        for item in reversed(history):
            if item.get("role") != role:
                continue
            match = re.search(r"(?:BUYER|SELLER)_PRICE\(\$?\s*([0-9]+(?:\.[0-9]+)?)", item.get("content", ""), re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None
