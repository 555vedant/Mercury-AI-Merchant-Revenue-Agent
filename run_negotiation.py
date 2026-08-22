from agenticpay import BuyerAgent, GeminiLLM, SellerAgent, make
from agenticpay.commerce import MerchantData
from agenticpay.revenue_engine import RevenueEngine

merchant = MerchantData(
    sku="WINTER-JACKET-001",
    list_price=140.00,
    unit_cost=68.00,
    fulfillment_cost=8.00,
    marketing_cost=4.00,
    minimum_margin_rate=0.20,
)
revenue_engine = RevenueEngine(merchant)
print("Merchant pricing:", revenue_engine.summary(), flush=True)

model = GeminiLLM(min_request_interval=13.0)
buyer = BuyerAgent(model, buyer_max_price=150)
seller = SellerAgent(model, seller_min_price=80, merchant_data=merchant)
env = make(
    "basic-price-negotiation-v0",
    buyer_agent=buyer,
    seller_agent=seller,
    max_rounds=4,
    initial_seller_price=merchant.list_price,
    buyer_max_price=150,
    seller_min_price=revenue_engine.minimum_viable_price,
)
observation, _ = env.reset(
    user_requirement="A waterproof winter jacket",
    product_info={"name": "Winter Jacket", "sku": merchant.sku, "features": ["waterproof", "insulated"]},
)

print("Starting buyer-seller negotiation...", flush=True)
while True:
    round_number = observation["current_round"] + 1
    print(f"\n--- Round {round_number} ---", flush=True)
    print("Buyer is thinking...", flush=True)
    buyer_action = buyer.respond(observation["conversation_history"], observation)
    print(f"Buyer: {buyer_action}", flush=True)
    seller_history = observation["conversation_history"] + [{"role": "buyer", "content": buyer_action}]
    print("Seller is thinking...", flush=True)
    seller_action = seller.respond(seller_history, observation)
    print(f"Seller: {seller_action}", flush=True)
    observation, _, terminated, truncated, info = env.step(buyer_action, seller_action)
    if terminated or truncated:
        print(f"\nNegotiation finished: {info}", flush=True)
        break
