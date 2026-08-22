from agenticpay.envs.registration import register, make, spec, pprint_registry, registry, EnvSpec
from agenticpay.envs.single_buyer_product_seller.Task1_basic_price_negotiation import Task1BasicPriceNegotiation
register(id="basic-price-negotiation-v0", entry_point="agenticpay.envs.single_buyer_product_seller.Task1_basic_price_negotiation:Task1BasicPriceNegotiation", max_episode_steps=8)
__all__ = ["register", "make", "spec", "pprint_registry", "registry", "EnvSpec", "Task1BasicPriceNegotiation"]
