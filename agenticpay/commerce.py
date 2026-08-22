"""Merchant inputs for one e-commerce product."""
from dataclasses import dataclass

@dataclass(frozen=True)
class MerchantData:
    sku: str
    list_price: float
    unit_cost: float
    fulfillment_cost: float = 0.0
    marketing_cost: float = 0.0
    minimum_margin_rate: float = 0.20

    @property
    def total_cost(self) -> float:
        return self.unit_cost + self.fulfillment_cost + self.marketing_cost
