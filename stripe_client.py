"""Stripe sale extraction.

In live mode (STRIPE_API_KEY, a test key is fine) this would list recent
Checkout Sessions / Invoices. For the demo it loads bundled samples in the same
shape Stripe returns, then normalizes to the facts the VAT/place-of-supply check
needs.

Stripe amounts are in the currency's smallest unit (cents); we divide by 100.
B2B vs B2C is inferred from whether the customer provided a VAT tax ID. Whether
`automatic_tax` was on tells us if Stripe even tried to compute tax.
"""

from __future__ import annotations

import json
import os

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")


def extract(source: str) -> list[dict]:
    if STRIPE_API_KEY:
        return _extract_live()
    with open(source) as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def _extract_live() -> list[dict]:  # pragma: no cover - needs a real (test) key
    """Live Stripe pull. Wired but inert until STRIPE_API_KEY is present.

        pip install stripe
    """
    import stripe  # type: ignore

    stripe.api_key = STRIPE_API_KEY
    out = []
    for s in stripe.checkout.Session.list(limit=25, expand=["data.customer_details"]).auto_paging_iter():
        out.append(s)
    return out


def normalize(sale: dict) -> dict:
    cust = sale.get("customer_details") or {}
    addr = cust.get("address") or {}
    tax_ids = cust.get("tax_ids") or []
    subtotal = float(sale.get("amount_subtotal", 0)) / 100.0
    tax = float((sale.get("total_details") or {}).get("amount_tax", 0)) / 100.0
    rate = (tax / subtotal) if subtotal else 0.0
    auto = sale.get("automatic_tax") or {}
    return {
        "seller_name": sale.get("seller_name", "Seller"),
        "seller_country": (sale.get("seller_country") or "").upper(),
        "customer_country": (addr.get("country") or "").upper(),
        "customer_vat_id": (tax_ids[0].get("value") if tax_ids else None),
        "product_type": (sale.get("product_type") or "digital").lower(),
        "currency": (sale.get("currency") or "eur").upper(),
        "net": subtotal,
        "tax_charged": tax,
        "tax_rate": rate,
        "stripe_tax_enabled": bool(auto.get("enabled")),
    }
