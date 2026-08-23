"""Razorpay Test Mode payment service."""

from __future__ import annotations

import hmac
import os

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from typing import Any, Optional

from dotenv import load_dotenv

from agenticpay.audit import AuditTrail
from agenticpay.payment_gate import create_razorpay_order
from agenticpay.policy_gate import PolicyResult

load_dotenv()


class RazorpayConfigurationError(RuntimeError):
    pass


class RazorpayVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class RazorpaySettings:
    key_id: str
    key_secret: str
    test_mode: bool = True

    @classmethod
    def from_env(cls) -> "RazorpaySettings":
        key_id = os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        test_mode = os.getenv("RAZORPAY_TEST_MODE", "true").lower() == "true"

        if not key_id or not key_secret:
            raise RazorpayConfigurationError(
                "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
            )

        if test_mode and not key_id.startswith("rzp_test_"):
            raise RazorpayConfigurationError(
                "RAZORPAY_TEST_MODE=true requires an rzp_test_ key ID."
            )

        return cls(
            key_id=key_id,
            key_secret=key_secret,
            test_mode=test_mode,
        )


@dataclass(frozen=True)
class RazorpayOrder:
    order_id: str
    amount_paise: int
    currency: str
    receipt: str
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "amount_paise": self.amount_paise,
            "currency": self.currency,
            "receipt": self.receipt,
            "status": self.status,
        }


class RazorpayPaymentService:
    def __init__(
        self,
        settings: RazorpaySettings,
        audit_trail: AuditTrail,
        client: Optional[Any] = None,
    ):
        self.settings = settings
        self.audit_trail = audit_trail

        if client is None:
            try:
                import razorpay
            except ImportError as error:
                raise ImportError(
                    "Install dependencies with: "
                    "python -m pip install -r requirements.txt"
                ) from error

            client = razorpay.Client(
                auth=(settings.key_id, settings.key_secret)
            )

        self.client = client
        self.orders: dict[str, RazorpayOrder] = {}
        self.payment_statuses: dict[str, str] = {}

    @staticmethod
    def rupees_to_paise(
        amount_rupees: Decimal | str | float | int,
    ) -> int:
        try:
            paise = (
                Decimal(str(amount_rupees)) * 100
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, ValueError) as error:
            raise ValueError(
                "Amount must be a valid INR amount."
            ) from error

        if paise <= 0:
            raise ValueError("Amount must be greater than zero.")

        return int(paise)

    def create_order(
        self,
        policy_result: PolicyResult,
        amount_rupees: Decimal | str | float | int,
        receipt: str,
        notes: Optional[dict[str, str]] = None,
    ) -> RazorpayOrder:
        amount_paise = self.rupees_to_paise(amount_rupees)

        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": notes or {},
        }

        response = create_razorpay_order(
            policy_result,
            self.client.order.create,
            data=order_data,
        )

        order = RazorpayOrder(
            order_id=response["id"],
            amount_paise=int(response["amount"]),
            currency=response["currency"],
            receipt=response.get("receipt", receipt),
            status=response.get("status", "created"),
        )

        self.orders[order.order_id] = order
        self.payment_statuses[order.order_id] = order.status

        self.audit_trail.record_payment_event(
            "razorpay_order_created",
            {
                **order.to_dict(),
                "policy": policy_result.to_dict(),
            },
        )

        return order

    def verify_checkout_payment(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> str:
        order = self.orders.get(razorpay_order_id)

        if order is None:
            raise RazorpayVerificationError(
                "Unknown Razorpay order ID."
            )

        message = (
            f"{razorpay_order_id}|{razorpay_payment_id}"
        ).encode()

        expected_signature = hmac.new(
            self.settings.key_secret.encode(),
            message,
            sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            expected_signature,
            razorpay_signature,
        ):
            self.audit_trail.record_payment_event(
                "razorpay_payment_verification_failed",
                {
                    "order_id": razorpay_order_id,
                    "payment_id": razorpay_payment_id,
                },
            )

            raise RazorpayVerificationError(
                "Invalid Razorpay checkout signature."
            )

        self.payment_statuses[razorpay_order_id] = "verified"

        self.audit_trail.record_payment_event(
            "razorpay_payment_verified",
            {
                "order_id": razorpay_order_id,
                "payment_id": razorpay_payment_id,
                "status": "verified",
            },
        )

        return "verified"