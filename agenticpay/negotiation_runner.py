"""Reusable orchestration for the existing buyer/seller negotiation environment."""
from typing import Any

from agenticpay.agents.base_agent import BaseAgent
from agenticpay.core import NegotiationStatus


def run_negotiation(
    env: Any,
    buyer_agent: BaseAgent,
    seller_agent: BaseAgent,
    user_requirement: str,
    product_info: dict[str, Any],
) -> dict[str, Any]:
    """Run the existing environment loop until agreement or timeout."""
    observation, _ = env.reset(user_requirement=user_requirement, product_info=product_info)
    while True:
        buyer_action = buyer_agent.respond(observation["conversation_history"], observation)
        seller_history = observation["conversation_history"] + [{"role": "buyer", "content": buyer_action}]
        seller_action = seller_agent.respond(seller_history, observation)
        observation, reward, terminated, truncated, info = env.step(buyer_action, seller_action)
        if terminated or truncated:
            return {
                "observation": observation,
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "info": info,
                "status": NegotiationStatus.AGREED.value if terminated else NegotiationStatus.TIMEOUT.value,
            }
