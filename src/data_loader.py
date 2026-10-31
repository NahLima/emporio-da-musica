"""Load, validate and normalize the Empório da Música challenge data.

The original CSVs in ``data/`` are never modified. This module reads them,
normalizes types, parses the JSON ``specs`` column, and records the data
quality problems that the agent must surface instead of hiding:

* order totals that disagree with the sum of their items (orders 3 and 20);
* product 130 (``coming_soon``) sold in orders 3 and 14;
* categories 6, 7 and 8 with zero products, although the store manual claims
  a catalog of 300+ instruments (the CSVs contain 65 products).
"""

from __future__ import annotations

import csv
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Data problems that cannot be detected by a rule alone, documented so the
# agent and the README can quote them instead of silently smoothing them away.
KNOWN_DATA_ISSUES = [
    "Bass products 135-138 have name/description mismatches "
    "(e.g. product 135 is named 'Music Man Bass 1X Electric Bass' but its "
    "description says 'Fender Jazz Bass'). The catalog name is authoritative; "
    "specs must not be invented from the description.",
    "The store manual claims 300+ instruments, but the CSV catalog has 65 "
    "products and categories 6 (woodwind), 7 (brass) and 8 (orchestral "
    "strings) have zero products.",
    "The manual gives two WhatsApp numbers ((67) 3341-4444 on the cover, "
    "(67) 3321-4500 in section 7) and an e-mail with an accent in section "
    "1.2. The cover values are used; the conflict is documented in the README.",
    "The CSVs have no delivery/receipt date. The return rules count 7 days "
    "from receipt, so estimated_delivery is used as a receipt proxy "
    "(falling back to order_date). See tools.check_return_eligibility.",
]


def normalize_text(text: str) -> str:
    """Lower-case, strip accents and collapse whitespace for matching."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(without_accents.lower().split())


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _parse_specs(raw: str) -> dict:
    """Parse the JSON specs column; return an empty dict on bad input."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class StoreData:
    """All normalized store data, plus the data-quality notes found."""

    products: list[dict] = field(default_factory=list)
    products_by_id: dict[int, dict] = field(default_factory=dict)
    categories: dict[int, dict] = field(default_factory=dict)
    customers: dict[int, dict] = field(default_factory=dict)
    orders: dict[int, dict] = field(default_factory=dict)
    order_items: dict[int, list[dict]] = field(default_factory=dict)
    promotions: list[dict] = field(default_factory=list)
    promotions_by_product: dict[int, list[dict]] = field(default_factory=dict)
    data_quality_notes: list[str] = field(default_factory=list)

    def product(self, product_id: int) -> dict | None:
        return self.products_by_id.get(product_id)

    def category_name(self, category_id: int) -> str | None:
        category = self.categories.get(category_id)
        return category["name"] if category else None


def load_store_data(data_dir: str | Path | None = None) -> StoreData:
    """Load and normalize every CSV under ``data_dir`` (default: repo data/)."""
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir = Path(data_dir)
    store = StoreData()
    store.data_quality_notes.extend(KNOWN_DATA_ISSUES)

    for row in _read_csv(data_dir / "categories.csv"):
        store.categories[int(row["category_id"])] = {
            "category_id": int(row["category_id"]),
            "name": row["name"].strip(),
            "description": row.get("description", "").strip(),
        }

    for row in _read_csv(data_dir / "products.csv"):
        product = {
            "product_id": int(row["product_id"]),
            "name": row["name"].strip(),
            "price_brl": round(float(row["price_brl"]), 2),
            "category_id": int(row["category_id"]),
            "category": store.category_name(int(row["category_id"])),
            "description": row.get("description", "").strip(),
            "stock_quantity": int(row["stock_quantity"]),
            "status": row["status"].strip().lower(),
            "specs": _parse_specs(row.get("specs", "")),
            "created_at": row.get("created_at", "").strip(),
        }
        # A product is buyable only when it is active AND in stock. The
        # catalog has two traps here: product 96 is active with stock 0 and
        # product 113 is discontinued with stock 0.
        product["buyable"] = (
            product["status"] == "active" and product["stock_quantity"] > 0
        )
        store.products.append(product)
        store.products_by_id[product["product_id"]] = product

    for row in _read_csv(data_dir / "customers.csv"):
        store.customers[int(row["customer_id"])] = {
            "customer_id": int(row["customer_id"]),
            "name": row["name"].strip(),
            "phone": row.get("phone", "").strip(),
            "email": row.get("email", "").strip(),
            "city": row.get("city", "").strip(),
        }

    for row in _read_csv(data_dir / "orders.csv"):
        store.orders[int(row["order_id"])] = {
            "order_id": int(row["order_id"]),
            "customer_id": int(row["customer_id"]),
            "order_date": row["order_date"].strip(),
            "status": row["status"].strip().lower(),
            "total_brl": round(float(row["total_brl"]), 2),
            "payment_method": row["payment_method"].strip(),
            "tracking_code": row.get("tracking_code", "").strip(),
            "estimated_delivery": row.get("estimated_delivery", "").strip(),
            "notes": row.get("notes", "").strip(),
        }

    for row in _read_csv(data_dir / "order_items.csv"):
        item = {
            "order_id": int(row["order_id"]),
            "product_id": int(row["product_id"]),
            "quantity": int(row["quantity"]),
        }
        store.order_items.setdefault(item["order_id"], []).append(item)

    for row in _read_csv(data_dir / "promotions.csv"):
        promotion = {
            "promotion_id": int(row["promotion_id"]),
            "product_id": int(row["product_id"]),
            "discount_percent": float(row["discount_percent"]),
            "description": row.get("description", "").strip(),
            "is_active": row["is_active"].strip() == "1",
        }
        store.promotions.append(promotion)
        store.promotions_by_product.setdefault(
            promotion["product_id"], []
        ).append(promotion)

    # --- Data-quality checks (computed, not assumed) ---------------------
    # 1. Order totals vs. the sum of their items.
    for order_id, order in store.orders.items():
        items_sum = round(
            sum(
                item["quantity"]
                * store.products_by_id[item["product_id"]]["price_brl"]
                for item in store.order_items.get(order_id, [])
                if item["product_id"] in store.products_by_id
            ),
            2,
        )
        if abs(items_sum - order["total_brl"]) > 0.01:
            store.data_quality_notes.append(
                f"Order {order_id}: total_brl is R$ {order['total_brl']:.2f} "
                f"but its items sum to R$ {items_sum:.2f} "
                f"(difference R$ {items_sum - order['total_brl']:+.2f}). "
                "The items sum is used; the CSV total is flagged, not trusted."
            )

    # 2. A coming_soon product that was sold.
    for order_id, items in store.order_items.items():
        for item in items:
            product = store.products_by_id.get(item["product_id"])
            if product and product["status"] == "coming_soon":
                store.data_quality_notes.append(
                    f"Order {order_id} sold product {product['product_id']} "
                    f"({product['name']}), which is marked coming_soon."
                )

    # 3. Categories with no products.
    for category_id, category in store.categories.items():
        if not any(
            product["category_id"] == category_id
            for product in store.products
        ):
            store.data_quality_notes.append(
                f"Category {category_id} ({category['name']}) has no products."
            )

    return store
