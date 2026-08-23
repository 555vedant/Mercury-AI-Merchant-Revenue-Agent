"""FastAPI endpoint for signed Razorpay webhooks."""
from fastapi import FastAPI, HTTPException, Request
from agenticpay.razorpay_payment import RazorpayPaymentService, RazorpayVerificationError


def create_webhook_app(payment_service: RazorpayPaymentService) -> FastAPI:
    app = FastAPI(title="Mercury Razorpay Webhooks")

    @app.post("/webhooks/razorpay")
    async def razorpay_webhook(request: Request) -> dict[str, str]:
        raw_body = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")
        try:
            return payment_service.handle_webhook(raw_body, signature)
        except RazorpayVerificationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return app
