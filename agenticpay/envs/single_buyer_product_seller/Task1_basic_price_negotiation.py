"""Single buyer and seller price-negotiation environment."""
import re
from typing import Any, Dict, Optional, Tuple
from agenticpay.core import BaseEnv, NegotiationInfo, NegotiationStatus
from agenticpay.agents.base_agent import BaseAgent
from agenticpay.memory.conversation_memory import ConversationMemory
from agenticpay.utils.negotiation_state import NegotiationState

class Task1BasicPriceNegotiation(BaseEnv):
    def __init__(self, buyer_agent: BaseAgent, seller_agent: BaseAgent, max_rounds: int = 8, initial_seller_price: float = 100.0, buyer_max_price: Optional[float] = None, seller_min_price: Optional[float] = None, environment_info: Optional[Dict[str, Any]] = None, price_tolerance: float = 1.0, **_: Any):
        super().__init__()
        self.buyer_agent, self.seller_agent = buyer_agent, seller_agent
        self.max_rounds, self.initial_seller_price = max_rounds, initial_seller_price
        self.buyer_max_price, self.seller_min_price = buyer_max_price, seller_min_price
        self.environment_info, self.price_tolerance = environment_info or {}, price_tolerance
        self.memory = ConversationMemory()
        self.state, self.negotiation_info, self.current_round = NegotiationState(), NegotiationInfo(), 0

    def reset(self, user_requirement: str = "", product_info: Optional[Dict[str, Any]] = None, user_profile: Optional[Any] = None, **_: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.memory.clear()
        self.state, self.negotiation_info, self.current_round = NegotiationState(), NegotiationInfo(), 0
        product_info = product_info or {}
        self.buyer_agent.initialize({"user_requirement": user_requirement, "product_info": product_info, "max_price": self.buyer_max_price, "user_profile": user_profile, "environment_info": self.environment_info})
        self.seller_agent.initialize({"product_info": product_info, "min_price": self.seller_min_price, "initial_price": self.initial_seller_price, "environment_info": self.environment_info})
        return self._observation(), self._info()

    def step(self, buyer_action: Optional[str] = None, seller_action: Optional[str] = None) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        if self.negotiation_info.status is not NegotiationStatus.ONGOING:
            raise RuntimeError("Negotiation has finished. Call reset() before stepping again.")
        if buyer_action:
            self.memory.add_message("buyer", buyer_action, self.current_round + 1)
            self.state.buyer_price = self._price(buyer_action, "BUYER")
        if seller_action:
            self.memory.add_message("seller", seller_action, self.current_round + 1)
            self.state.seller_price = self._price(seller_action, "SELLER")
        self.current_round += 1
        self.state.round = self.current_round
        agreed = self.state.buyer_price is not None and self.state.seller_price is not None and self.state.seller_price <= self.state.buyer_price + self.price_tolerance
        if agreed:
            self.state.agreed_price = self.state.seller_price if self.state.seller_price <= self.state.buyer_price else (self.state.buyer_price + self.state.seller_price) / 2
            self.negotiation_info.status = NegotiationStatus.AGREED
        elif self.current_round >= self.max_rounds:
            self.negotiation_info.status = NegotiationStatus.TIMEOUT
        self.negotiation_info.buyer_price, self.negotiation_info.seller_price = self.state.buyer_price, self.state.seller_price
        self.negotiation_info.current_price, self.negotiation_info.round_count = self.state.agreed_price or self.state.seller_price or self.state.buyer_price, self.current_round
        self.negotiation_info.conversation_history = self.memory.get_history()
        terminated = self.negotiation_info.status is NegotiationStatus.AGREED
        truncated = self.negotiation_info.status is NegotiationStatus.TIMEOUT
        reward = 1.0 if terminated else 0.0
        return self._observation(), reward, terminated, truncated, self._info()

    @staticmethod
    def _price(message: str, role: str) -> Optional[float]:
        match = re.search(rf"###\s*{role}_PRICE\(\$?\s*([0-9]+(?:\.[0-9]+)?)\s*\)\s*###", message, re.IGNORECASE)
        return float(match.group(1)) if match else None

    def _observation(self) -> Dict[str, Any]:
        return {"conversation_history": self.memory.get_history(), "current_round": self.current_round, "buyer_price": self.state.buyer_price, "seller_price": self.state.seller_price, "status": self.negotiation_info.status.value}
    def _info(self) -> Dict[str, Any]:
        return {"status": self.negotiation_info.status.value, "agreed_price": self.state.agreed_price, "round_count": self.current_round, "seller_revenue": getattr(self.seller_agent, "last_decision", {})}
    def render(self, mode: str = "human") -> Optional[str]:
        text = "\n".join(f"{m['role'].title()}: {m['content']}" for m in self.memory.get_history())
        if mode == "text": return text
        print(text)
        return None

