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

    def best_offer(self, buyer_max_price: float, quantity: int = 1, candidate_count: int = 5) -> Dict[str, float]:
        """Return the highest-profit profitable candidate within the buyer's budget."""
        if buyer_max_price < self.minimum_viable_price:
            raise ValueError("buyer_max_price must be at least the minimum viable price.")
        if candidate_count <= 0:
            raise ValueError("candidate_count must be positive.")

        minimum_price = self.minimum_viable_price
        if candidate_count == 1 or buyer_max_price == minimum_price:
            candidates = [minimum_price]
        else:
            step = (buyer_max_price - minimum_price) / (candidate_count - 1)
            candidates = [minimum_price + step * index for index in range(candidate_count)]

        offers = [self.evaluate(round(price, 2), quantity) for price in candidates]
        profitable = [offer for offer in offers if offer["profit"] > 0]
        if not profitable:
            raise ValueError("No profitable offer is available within the buyer's budget.")
        best = max(profitable, key=lambda offer: (offer["profit"], -offer["revenue"]))
        return {
            "recommended_price": best["revenue"] / quantity,
            "profit": best["profit"],
            "revenue": best["revenue"],
            "margin_rate": best["margin_rate"],
        }

    def summary(self) -> Dict[str, object]:
        return {"merchant": asdict(self.merchant), "minimum_viable_price": round(self.minimum_viable_price, 2), "target_price": round(self.target_price, 2)}
