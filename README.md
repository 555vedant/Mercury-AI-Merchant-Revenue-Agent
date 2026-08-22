# AgenticPay

A small, Gemini-powered buyer/seller price-negotiation core.

## Setup

```powershell
pip install -r requirements.txt
$env:GEMINI_API_KEY = "your-key"
python run_negotiation.py
```

The default model is `gemini-3.6-flash`.

The project contains a single bilateral environment (`basic-price-negotiation-v0`), `BuyerAgent`, `SellerAgent`, and `GeminiLLM`. Agents must emit price tags: `### BUYER_PRICE($amount) ###` and `### SELLER_PRICE($amount) ###`.
