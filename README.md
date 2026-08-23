# AgenticPay

A small, Gemini-powered buyer/seller price-negotiation core.

## Setup

```powershell
pip install -r requirements.txt
$env:GEMINI_API_KEY = "your-key"
$env:RAZORPAY_KEY_ID = "rzp_test_your_key_id"
$env:RAZORPAY_KEY_SECRET = "your_test_key_secret"
python run_negotiation.py
```

The default model is the lightweight `gemini-3.5-flash-lite`. Price decisions are deterministic; if Gemini returns no text, the agents use a built-in fallback sentence and continue negotiating.

To create a Razorpay Test Mode order after an allowed negotiation, opt in explicitly:

```powershell
$env:CREATE_RAZORPAY_TEST_ORDER = "true"
python run_negotiation.py
```

The runner evaluates the `PolicyGate` first. `BLOCK` and `HUMAN_APPROVAL` results do not call Razorpay. The order amount is converted from rupees to paise and the returned result contains `order_id`, `amount`, `currency`, and `status`.

The project contains a single bilateral environment (`basic-price-negotiation-v0`), `BuyerAgent`, `SellerAgent`, and `GeminiLLM`. Agents must emit price tags: `### BUYER_PRICE($amount) ###` and `### SELLER_PRICE($amount) ###`.

## API

Start the minimal FastAPI backend:

```powershell
uvicorn api:app --reload
```

It provides `POST /negotiate`, `POST /payment/create`, `GET /negotiation/{id}`, and `POST /webhooks/razorpay`. Negotiations and audit records are kept in memory only. A payment order is created only when the stored negotiation has an `ALLOW` policy result.
