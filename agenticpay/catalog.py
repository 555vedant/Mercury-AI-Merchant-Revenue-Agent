"""Small in-memory merchant catalog for one-product negotiations."""
from dataclasses import asdict
from typing import Any

from agenticpay.commerce import MerchantData


CATALOG: tuple[MerchantData, ...] = (
    MerchantData("WINTER-JACKET-001", 140.00, 68.00, 8.00, 4.00, 0.20, "apparel", 12),
    MerchantData("TRAVEL-BACKPACK-002", 95.00, 42.00, 6.00, 3.00, 0.20, "bags", 25),
    MerchantData("RUNNING-SHOES-003", 120.00, 58.00, 7.00, 5.00, 0.20, "footwear", 18),
    MerchantData("STUDIO-HEADPHONES-004", 180.00, 92.00, 5.00, 6.00, 0.20, "electronics", 9),
    MerchantData("SMART-WATCH-005", 220.00, 120.00, 5.00, 8.00, 0.20, "electronics", 7),
    MerchantData("CERAMIC-MUG-006", 28.00, 9.00, 3.00, 2.00, 0.20, "home", 40),
)

FEATURES: dict[str, tuple[str, ...]] = {
    "WINTER-JACKET-001": ("waterproof", "insulated"),
    "TRAVEL-BACKPACK-002": ("24L capacity", "laptop sleeve"),
    "RUNNING-SHOES-003": ("lightweight", "breathable mesh"),
    "STUDIO-HEADPHONES-004": ("noise cancelling", "40-hour battery"),
    "SMART-WATCH-005": ("heart-rate tracking", "GPS"),
    "CERAMIC-MUG-006": ("dishwasher safe", "350ml capacity"),
}


def catalog_items() -> list[dict[str, Any]]:
    """Return serializable catalog items for the API."""
    return [
        {**asdict(product), "name": product_name(product.sku), "features": list(FEATURES[product.sku])}
        for product in CATALOG
    ]


def get_product(sku: str) -> MerchantData:
    """Resolve exactly one catalog product by SKU."""
    normalized_sku = sku.strip().upper()
    for product in CATALOG:
        if product.sku == normalized_sku:
            return product
    raise KeyError(normalized_sku)


def product_name(sku: str) -> str:
    names = {
        "WINTER-JACKET-001": "Waterproof Winter Jacket",
        "TRAVEL-BACKPACK-002": "Everyday Travel Backpack",
        "RUNNING-SHOES-003": "Velocity Running Shoes",
        "STUDIO-HEADPHONES-004": "Studio Wireless Headphones",
        "SMART-WATCH-005": "Pulse Smart Watch",
        "CERAMIC-MUG-006": "Stoneware Coffee Mug",
    }
    return names[sku]
