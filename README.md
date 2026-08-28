# Mercury — Autonomous AI Merchant

Mercury is an AI-powered merchant agent that negotiates with AI buyers to increase merchant revenue while keeping every deal within strict profit and policy limits.

### What it does

- AI buyer and merchant negotiation
- Reinforcement learning for merchant strategy
- Customer Value Optimization (CVO)
- Deterministic revenue and margin guardrails
- Policy-gated transactions
- Razorpay Test Mode order creation
- Explainable audit trail for every money decision

### Tech Stack

Python · FastAPI · Gemini · Q-Learning · SQLite · Razorpay Test Mode

### Core Flow

`Buyer Agent → Negotiation → RL Merchant Agent → Revenue Engine → Policy Gate → Razorpay`

After each completed negotiation, the merchant receives a reward based on conversion, profit, and margin, then updates its persistent Q-table to improve future decisions.

> **Note:** Razorpay integration runs in Test Mode. No real money is involved.
