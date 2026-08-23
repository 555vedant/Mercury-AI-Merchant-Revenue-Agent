"""Small HTTP API for Mercury negotiations and Razorpay Test Mode payments."""
import hashlib
import hmac
import json
import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agenticpay import (
    AuditTrail,
    BuyerAgent,
    GeminiLLM,
    MerchantData,
    PolicyConfig,
    PolicyContext,
    PolicyDecision,
    PolicyGate,
    RevenueEngine,
    SellerAgent,
    create_razorpay_test_order,
    make,
)
from agenticpay.negotiation_runner import run_negotiation

app = FastAPI(title="Mercury API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173 ,http://127.0.0.1:8000/payment/create"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Razorpay-Signature"],
)

merchant = MerchantData(
    sku="WINTER-JACKET-001",
    list_price=140.00,
    unit_cost=68.00,
    fulfillment_cost=8.00,
    marketing_cost=4.00,
    minimum_margin_rate=0.20,
    category="apparel",
    inventory_quantity=12,
)
revenue_engine = RevenueEngine(merchant)
policy_gate = PolicyGate(
    PolicyConfig(
        maximum_autonomous_amount=50000.00,
        human_approval_amount=25000.00,
        minimum_margin_rate=0.15,
        maximum_discount_rate=0.30,
        blocked_categories=frozenset({"restricted"}),
    )
)
model = GeminiLLM(min_request_interval=13.0)
negotiations: dict[str, dict[str, Any]] = {}


class NegotiateRequest(BaseModel):
    user_requirement: str = Field(min_length=1)
    product_info: dict[str, Any] = Field(default_factory=dict)
    buyer_max_price: float = Field(default=150.0, gt=0)
    max_rounds: int = Field(default=4, ge=1, le=8)


class PaymentCreateRequest(BaseModel):
    negotiation_id: str
    receipt: str = Field(default="mercury-api-order", min_length=1)


def _policy_for(result: dict[str, Any]) -> Any:
    info = result["info"]
    return policy_gate.evaluate(
        PolicyContext(
            agreed_price=info["agreed_price"],
            quantity=1,
            category=merchant.category,
            merchant=merchant,
        )
    )


def _negotiation_response(negotiation_id: str, record: dict[str, Any]) -> dict[str, Any]:
    result = record["result"]
    policy_result = record["policy_result"]
    return {
        "negotiation_id": negotiation_id,
        "status": result["status"],
        "agreed_price": result["info"]["agreed_price"],
        "merchant": revenue_engine.summary(),
        "revenue": result["info"].get("seller_revenue", {}),
        "policy": policy_result.to_dict() if policy_result else None,
        "audit_trail": record["audit_trail"].as_dicts(),
        "conversation_history": result["observation"]["conversation_history"],
    }


@app.post("/negotiate")
def negotiate(request: NegotiateRequest) -> dict[str, Any]:
    buyer = BuyerAgent(model, buyer_max_price=request.buyer_max_price)
    seller = SellerAgent(model, merchant_data=merchant)
    env = make(
        "basic-price-negotiation-v0",
        buyer_agent=buyer,
        seller_agent=seller,
        max_rounds=request.max_rounds,
        initial_seller_price=merchant.list_price,
        buyer_max_price=request.buyer_max_price,
        seller_min_price=revenue_engine.minimum_viable_price,
    )
    result = run_negotiation(env, buyer, seller, request.user_requirement, request.product_info)
    negotiation_id = str(uuid4())
    policy_result = _policy_for(result) if result["terminated"] else None
    audit_trail = AuditTrail()
    if policy_result is not None:
        audit_trail.record_policy_decision(policy_result)
    negotiations[negotiation_id] = {
        "result": result,
        "policy_result": policy_result,
        "audit_trail": audit_trail,
    }
    return _negotiation_response(negotiation_id, negotiations[negotiation_id])


@app.post("/payment/create")
def create_payment(request: PaymentCreateRequest) -> dict[str, Any]:
    negotiation = negotiations.get(request.negotiation_id)
    if negotiation is None:
        raise HTTPException(status_code=404, detail="Negotiation not found.")
    policy_result = negotiation["policy_result"]
    if policy_result is None:
        raise HTTPException(status_code=409, detail="Payment requires an agreed negotiation.")
    if policy_result.decision is not PolicyDecision.ALLOW:
        raise HTTPException(status_code=403, detail=policy_result.reason)
    try:
        return create_razorpay_test_order(policy_result, receipt=request.receipt)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request) -> dict[str, Any]:
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not signature or not secret:
        raise HTTPException(status_code=400, detail="Razorpay webhook signature configuration is missing.")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature.")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Webhook body must be valid JSON.") from error
    return {"received": True, "event": payload.get("event")}


@app.get("/negotiation/{negotiation_id}")
def get_negotiation(negotiation_id: str) -> dict[str, Any]:
    negotiation = negotiations.get(negotiation_id)
    if negotiation is None:
        raise HTTPException(status_code=404, detail="Negotiation not found.")
    return _negotiation_response(negotiation_id, negotiation)
