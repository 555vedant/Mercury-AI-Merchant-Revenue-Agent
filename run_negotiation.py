from agenticpay import AuditTrail, BuyerAgent, GeminiLLM, MerchantData, PolicyConfig, PolicyContext, PolicyGate, RevenueEngine, SellerAgent, make

merchant = MerchantData(sku="WINTER-JACKET-001", list_price=140.00, unit_cost=68.00, fulfillment_cost=8.00, marketing_cost=4.00, minimum_margin_rate=0.20, category="apparel", inventory_quantity=12)
revenue_engine = RevenueEngine(merchant)
policy_gate = PolicyGate(PolicyConfig(maximum_autonomous_amount=50000.00, human_approval_amount=25000.00, minimum_margin_rate=0.15, maximum_discount_rate=0.30, blocked_categories=frozenset({"restricted"})))
audit_trail = AuditTrail()
print("Merchant pricing:", revenue_engine.summary(), flush=True)

model = GeminiLLM(min_request_interval=13.0)
buyer = BuyerAgent(model, buyer_max_price=150)
seller = SellerAgent(model, seller_min_price=80, merchant_data=merchant)
env = make("basic-price-negotiation-v0", buyer_agent=buyer, seller_agent=seller, max_rounds=4, initial_seller_price=merchant.list_price, buyer_max_price=150, seller_min_price=revenue_engine.minimum_viable_price)
observation, _ = env.reset(user_requirement="A waterproof winter jacket", product_info={"name": "Winter Jacket", "sku": merchant.sku, "category": merchant.category, "features": ["waterproof", "insulated"]})

print("Starting buyer-seller negotiation...", flush=True)
while True:
    round_number = observation["current_round"] + 1
    print(f"\n--- Round {round_number} ---", flush=True)
    buyer_action = buyer.respond(observation["conversation_history"], observation)
    print(f"Buyer: {buyer_action}", flush=True)
    seller_history = observation["conversation_history"] + [{"role": "buyer", "content": buyer_action}]
    seller_action = seller.respond(seller_history, observation)
    print(f"Seller: {seller_action}", flush=True)
    observation, _, terminated, truncated, info = env.step(buyer_action, seller_action)
    if terminated or truncated:
        print(f"\nNegotiation finished: {info}", flush=True)
        if terminated:
            policy_result = policy_gate.evaluate(PolicyContext(agreed_price=info["agreed_price"], quantity=1, category=merchant.category, merchant=merchant))
            audit_trail.record_policy_decision(policy_result)
            print("Policy decision:", policy_result.to_dict(), flush=True)
        break
