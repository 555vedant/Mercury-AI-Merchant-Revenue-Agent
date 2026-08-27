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

from database.database import (
    create_customer,
    get_connection,
    get_customer,
    init_db,
    save_audit,
    save_negotiation,
    save_payment,
    update_customer,
)

from agenticpay import (
    AuditTrail,
    BuyerAgent,
    GeminiLLM,
    PolicyConfig,
    PolicyContext,
    PolicyDecision,
    PolicyGate,
    RevenueEngine,
    SellerAgent,
    catalog_items,
    create_razorpay_test_order,
    get_product,
    make,
    product_name,
)

from agenticpay.catalog import FEATURES
from agenticpay.merchant_policy import MerchantPolicy
from agenticpay.negotiation_runner import run_negotiation


app = FastAPI(title="Mercury API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Content-Type",
        "X-Razorpay-Signature",
    ],
)


init_db()

model = GeminiLLM(
    min_request_interval=13.0
)

negotiations: dict[str, dict[str, Any]] = {}


# =============================================================
# REQUEST MODELS
# =============================================================

class NegotiateRequest(BaseModel):

    customer_id: str | None = None

    user_requirement: str = Field(
        min_length=1
    )

    product_sku: str = Field(
        min_length=1
    )

    buyer_max_price: float = Field(
        default=150.0,
        gt=0,
    )

    max_rounds: int = Field(
        default=4,
        ge=1,
        le=8,
    )

    cvo_enabled: bool = Field(
        default=False
    )


class PaymentCreateRequest(BaseModel):

    negotiation_id: str

    receipt: str = Field(
        default="mercury-api-order",
        min_length=1,
    )


# =============================================================
# POLICY
# =============================================================

def _policy_for(
    result: dict[str, Any],
    merchant: Any,
    policy_gate: PolicyGate,
) -> Any:

    return policy_gate.evaluate(
        PolicyContext(
            agreed_price=result["info"]["agreed_price"],
            quantity=1,
            category=merchant.category,
            merchant=merchant,
        )
    )


# =============================================================
# AUDIT PERSISTENCE
# =============================================================

def _save_audit_trail(
    audit_trail: AuditTrail,
    customer_id: str,
) -> None:

    for entry in audit_trail.as_dicts():

        save_audit(
            event=entry.get(
                "event",
                "UNKNOWN",
            ),
            details=json.dumps(
                {
                    "customer_id": customer_id,
                    **entry,
                },
                default=str,
            ),
        )


# =============================================================
# RESPONSE
# =============================================================

def _negotiation_response(
    negotiation_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:

    result = record["result"]
    policy_result = record["policy_result"]

    return {
        "negotiation_id": negotiation_id,
        "customer_id": record["customer_id"],
        "status": result["status"],
        "agreed_price": result["info"]["agreed_price"],
        "merchant": record["revenue_engine"].summary(),
        "revenue": result["info"].get(
            "seller_revenue",
            {},
        ),
        "policy": (
            policy_result.to_dict()
            if policy_result
            else None
        ),
        "audit_trail": (
            record["audit_trail"].as_dicts()
        ),
        "learning_metrics": (
            MerchantPolicy().metric_summary()
        ),
        "conversation_history": (
            result["observation"][
                "conversation_history"
            ]
        ),
    }


# =============================================================
# CUSTOMER
# =============================================================

@app.post("/customer")
def register_customer(
    customer_id: str,
) -> dict[str, str]:

    create_customer(customer_id)

    return {
        "customer_id": customer_id,
    }


@app.get("/customer/{customer_id}")
def get_customer_data(
    customer_id: str,
) -> dict[str, float | int | str]:

    customer = get_customer(
        customer_id
    )

    if customer is None:

        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    total_spend = float(
        customer["total_spend"]
    )

    total_profit = float(
        customer["total_profit"]
    )

    total_orders = int(
        customer["total_orders"]
    )

    clv_score = round(
        total_profit * 0.3
        + total_spend * 0.6
        + total_orders * 10,
        2,
    )

    return {
        "customer_id": customer_id,
        "total_orders": total_orders,
        "total_spend": total_spend,
        "total_profit": total_profit,
        "clv_score": clv_score,
    }


@app.get("/customer/{customer_id}/history")
def get_customer_history(
    customer_id: str,
) -> dict[str, list[dict[str, Any]]]:

    conn = get_connection()

    negotiations_rows = conn.execute(
        """
        SELECT sku, final_price, status, created_at
        FROM negotiations
        WHERE customer_id = ?
        ORDER BY created_at DESC
        """,
        (customer_id,),
    ).fetchall()

    payments_rows = conn.execute(
        """
        SELECT order_id, amount, status, created_at
        FROM payments
        WHERE customer_id = ?
        ORDER BY created_at DESC
        """,
        (customer_id,),
    ).fetchall()

    conn.close()

    return {
        "negotiations": [
            dict(row)
            for row in negotiations_rows
        ],
        "payments": [
            dict(row)
            for row in payments_rows
        ],
    }


@app.get("/customer/{customer_id}/audit")
def get_customer_audit(
    customer_id: str,
) -> dict[str, list[dict[str, Any]]]:

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT event, details, created_at
        FROM audit_events
        WHERE details LIKE ?
        ORDER BY created_at DESC
        """,
        (
            f'%"customer_id": "{customer_id}"%',
        ),
    ).fetchall()

    conn.close()

    return {
        "audit": [
            dict(row)
            for row in rows
        ],
    }


# =============================================================
# CATALOG
# =============================================================

@app.get("/catalog")
def get_catalog() -> list[dict[str, Any]]:

    return catalog_items()


# =============================================================
# NEGOTIATION
# =============================================================

@app.post("/negotiate")
def negotiate(
    request: NegotiateRequest,
) -> dict[str, Any]:

    try:

        merchant = get_product(
            request.product_sku
        )

    except KeyError as error:

        raise HTTPException(
            status_code=404,
            detail=(
                "Product SKU not found: "
                f"{request.product_sku}"
            ),
        ) from error

    customer_id = (
        request.customer_id
        or str(uuid4())
    )

    create_customer(
        customer_id
    )

    # ---------------------------------------------------------
    # CVO
    # ---------------------------------------------------------

    clv_score = None

    if request.cvo_enabled:

        customer = get_customer(
            customer_id
        )

        if customer:

            total_spend = float(
                customer["total_spend"]
            )

            total_profit = float(
                customer["total_profit"]
            )

            total_orders = int(
                customer["total_orders"]
            )

            clv_score = round(
                total_profit * 0.3
                + total_spend * 0.6
                + total_orders * 10,
                2,
            )

    # ---------------------------------------------------------
    # REVENUE ENGINE
    # ---------------------------------------------------------

    revenue_engine = RevenueEngine(
        merchant
    )

    # ---------------------------------------------------------
    # POLICY GATE
    # ---------------------------------------------------------

    policy_gate = PolicyGate(
        PolicyConfig(
            maximum_autonomous_amount=50000.00,
            human_approval_amount=25000.00,
            minimum_margin_rate=0.15,
            maximum_discount_rate=0.30,
            blocked_categories=frozenset(
                {"restricted"}
            ),
        )
    )

    # ---------------------------------------------------------
    # PRODUCT
    # ---------------------------------------------------------

    product_info = {
        "name": product_name(
            merchant.sku
        ),
        "sku": merchant.sku,
        "category": merchant.category,
        "features": list(
            FEATURES[merchant.sku]
        ),
    }

    # ---------------------------------------------------------
    # BUYER
    # ---------------------------------------------------------

    buyer = BuyerAgent(
        model,
        buyer_max_price=(
            request.buyer_max_price
        ),
    )

    audit_trail = AuditTrail()

    # ---------------------------------------------------------
    # SELLER
    # ---------------------------------------------------------

    seller = SellerAgent(
        model,
        merchant_data=merchant,
        merchant_policy=MerchantPolicy(
            exploration=0.15
        ),
        policy_gate=policy_gate,
        audit_trail=audit_trail,
        clv_score=clv_score,
        cvo_threshold=50.0,
        cvo_max_concession_rate=0.05,
    )

    # ---------------------------------------------------------
    # ENVIRONMENT
    # ---------------------------------------------------------

    env = make(
        "basic-price-negotiation-v0",
        buyer_agent=buyer,
        seller_agent=seller,
        max_rounds=request.max_rounds,
        initial_seller_price=(
            merchant.list_price
        ),
        buyer_max_price=(
            request.buyer_max_price
        ),
        seller_min_price=(
            revenue_engine.minimum_viable_price
        ),
    )

    # ---------------------------------------------------------
    # RUN
    # ---------------------------------------------------------

    result = run_negotiation(
        env,
        buyer,
        seller,
        request.user_requirement,
        product_info,
    )

    negotiation_id = str(uuid4())

    # ---------------------------------------------------------
    # FINAL POLICY DECISION
    # ---------------------------------------------------------

    policy_result = (
        _policy_for(
            result,
            merchant,
            policy_gate,
        )
        if result["terminated"]
        else None
    )

    if policy_result is not None:

        agreed_price = (
            result["info"].get(
                "agreed_price"
            )
        )

        audit_trail.record_policy_decision(
            policy_result,
            product=(
                product_info.get("name")
                or merchant.sku
            ),
            agreed_price=agreed_price,
            attempted_price=(
                result["observation"].get(
                    "buyer_price"
                )
                or result["observation"].get(
                    "seller_price"
                )
            ),
            inventory=(
                merchant.inventory_quantity
            ),
            margin=(
                result["info"]
                .get("seller_revenue", {})
                .get("margin_rate")
            ),
            discount=(
                max(
                    0.0,
                    (
                        merchant.list_price
                        - (
                            agreed_price
                            or merchant.list_price
                        )
                    )
                    / merchant.list_price,
                )
                if merchant.list_price
                else 0.0
            ),
            amount=agreed_price,
        )

    # ---------------------------------------------------------
    # AGREEMENT AUDIT
    # ---------------------------------------------------------

    if result["status"] == "agreed":

        audit_trail.record_negotiation_event(
            "AGREED",
            (
                "Offer accepted and the agreed "
                "price is within the merchant policy."
            ),
            product=(
                product_info.get("name")
                or merchant.sku
            ),
            agreed_price=(
                result["info"]
                .get("agreed_price")
            ),
            attempted_price=(
                result["observation"].get(
                    "buyer_price"
                )
                or result["observation"].get(
                    "seller_price"
                )
            ),
            inventory=(
                merchant.inventory_quantity
            ),
            margin=(
                result["info"]
                .get("seller_revenue", {})
                .get("margin_rate")
            ),
            amount=(
                result["info"]
                .get("agreed_price")
            ),
        )

    elif result["status"] == "timeout":

        audit_trail.record_negotiation_event(
            "TIMEOUT",
            (
                "Negotiation timed out without "
                "a valid agreement."
            ),
            product=(
                product_info.get("name")
                or merchant.sku
            ),
            attempted_price=(
                result["observation"].get(
                    "buyer_price"
                )
                or result["observation"].get(
                    "seller_price"
                )
            ),
            inventory=(
                merchant.inventory_quantity
            ),
            margin=(
                result["info"]
                .get("seller_revenue", {})
                .get("margin_rate")
            ),
            amount=(
                result["info"].get(
                    "agreed_price"
                )
                or result["observation"].get(
                    "buyer_price"
                )
                or result["observation"].get(
                    "seller_price"
                )
            ),
        )

    # ---------------------------------------------------------
    # STORE NEGOTIATION
    # ---------------------------------------------------------

    negotiations[negotiation_id] = {
        "result": result,
        "merchant": merchant,
        "revenue_engine": revenue_engine,
        "policy_gate": policy_gate,
        "policy_result": policy_result,
        "audit_trail": audit_trail,
        "customer_id": customer_id,
    }

    final_price = (
        result["info"].get(
            "agreed_price"
        )
    )

    save_negotiation(
        customer_id=customer_id,
        sku=merchant.sku,
        final_price=final_price,
        status=result["status"],
    )

    _save_audit_trail(
        audit_trail,
        customer_id,
    )

    return _negotiation_response(
        negotiation_id,
        negotiations[negotiation_id],
    )


# =============================================================
# PAYMENT
# =============================================================

@app.post("/payment/create")
def create_payment(
    request: PaymentCreateRequest,
) -> dict[str, Any]:

    negotiation = negotiations.get(
        request.negotiation_id
    )

    if negotiation is None:

        raise HTTPException(
            status_code=404,
            detail="Negotiation not found.",
        )

    policy_result = (
        negotiation["policy_result"]
    )

    if policy_result is None:

        raise HTTPException(
            status_code=409,
            detail=(
                "Payment requires an "
                "agreed negotiation."
            ),
        )

    if (
        policy_result.decision
        is not PolicyDecision.ALLOW
    ):

        raise HTTPException(
            status_code=403,
            detail=policy_result.reason,
        )

    customer_id = (
        negotiation["customer_id"]
    )

    try:

        order = create_razorpay_test_order(
            policy_result,
            receipt=request.receipt,
        )

        negotiation[
            "audit_trail"
        ].record_payment_event(
            "CREATED",
            (
                "Payment order created in "
                "Razorpay test mode after "
                "policy approval."
            ),
            product=(
                negotiation["merchant"].sku
            ),
            agreed_price=(
                policy_result.transaction_amount
            ),
            amount=(
                policy_result.transaction_amount
            ),
            order_id=order.get("order_id"),
            currency=order.get("currency"),
        )

        amount = float(
            policy_result.transaction_amount
        )

        revenue = (
            negotiation["result"]["info"]
            .get("seller_revenue", {})
        )

        profit = float(
            revenue.get(
                "profit",
                0.0,
            )
        )

        save_payment(
            customer_id=customer_id,
            order_id=order.get(
                "order_id",
                "",
            ),
            amount=amount,
            status=order.get(
                "status",
                "created",
            ),
        )

        update_customer(
            customer_id=customer_id,
            spend=amount,
            profit=profit,
        )

        _save_audit_trail(
            negotiation["audit_trail"],
            customer_id,
        )

        return order

    except (
        ValueError,
        RuntimeError,
    ) as error:

        negotiation[
            "audit_trail"
        ].record_payment_event(
            "FAILED",
            f"Payment creation failed: {error}",
            product=(
                negotiation["merchant"].sku
            ),
            agreed_price=(
                policy_result.transaction_amount
            ),
            amount=(
                policy_result.transaction_amount
            ),
        )

        save_payment(
            customer_id=customer_id,
            order_id=request.receipt,
            amount=float(
                policy_result.transaction_amount
            ),
            status="failed",
        )

        _save_audit_trail(
            negotiation["audit_trail"],
            customer_id,
        )

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


# =============================================================
# WEBHOOK
# =============================================================

@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
) -> dict[str, Any]:

    body = await request.body()

    signature = request.headers.get(
        "x-razorpay-signature"
    )

    secret = os.getenv(
        "RAZORPAY_WEBHOOK_SECRET"
    )

    if not signature or not secret:

        raise HTTPException(
            status_code=400,
            detail=(
                "Razorpay webhook signature "
                "configuration is missing."
            ),
        )

    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected,
        signature,
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Razorpay webhook signature."
            ),
        )

    try:

        payload = json.loads(body)

    except json.JSONDecodeError as error:

        raise HTTPException(
            status_code=400,
            detail=(
                "Webhook body must be valid JSON."
            ),
        ) from error

    save_audit(
        event="RAZORPAY_WEBHOOK",
        details=json.dumps(payload),
    )

    return {
        "received": True,
        "event": payload.get("event"),
    }


# =============================================================
# GET NEGOTIATION
# =============================================================

@app.get("/negotiation/{negotiation_id}")
def get_negotiation(
    negotiation_id: str,
) -> dict[str, Any]:

    negotiation = negotiations.get(
        negotiation_id
    )

    if negotiation is None:

        raise HTTPException(
            status_code=404,
            detail="Negotiation not found.",
        )

    return _negotiation_response(
        negotiation_id,
        negotiation,
    )