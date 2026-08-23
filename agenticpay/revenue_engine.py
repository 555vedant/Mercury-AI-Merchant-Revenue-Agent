"""Seller-side revenue calculations for the e-commerce environment."""
from dataclasses import asdict
from typing import Dict
from agenticpay.commerce import MerchantData

class RevenueEngine:
    def __init__(self, merchant: MerchantData):
        self.merchant = merchant

    @property
    def minimum_viable_price(self) -> float:
        margin = self.merchant.minimum_margin_rate
        if not 0 <= margin < 1:
            raise ValueError("minimum_margin_rate must be at least 0 and below 1.")
        return self.merchant.total_cost / (1 - margin)

    @property
    def target_price(self) -> float:
        return max(self.merchant.list_price, self.minimum_viable_price)

    def evaluate(self, price: float, quantity: int = 1) -> Dict[str, float]:
        if quantity <= 0:
            raise ValueError("quantity must be positive.")
        revenue = float(price) * quantity
        cost = self.merchant.total_cost * quantity
        profit = revenue - cost
        return {"revenue": round(revenue, 2), "cost": round(cost, 2), "profit": round(profit, 2), "margin_rate": round(profit / revenue, 4) if revenue else 0.0}

    def summary(self) -> Dict[str, object]:
        return {"merchant": asdict(self.merchant), "minimum_viable_price": round(self.minimum_viable_price, 2), "target_price": round(self.target_price, 2)}
