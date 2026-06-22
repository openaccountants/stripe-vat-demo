#!/usr/bin/env python3
"""Stripe -> OpenAccountants VAT place-of-supply pipeline.

    python pipeline.py                  # bundled sample sales (mock mode)
    python pipeline.py samples/sales.json

The flow:
    Stripe sales -> OA MCP (start -> get_skill) -> place-of-supply check -> verdict

Live: set OA_MCP_TOKEN (+ STRIPE_API_KEY, a test key works) to pull real
Checkout Sessions and verified rules instead of the bundled samples.
"""

from __future__ import annotations

import os
import sys

import stripe_client
import vat_check
from oa_client import OAClient

STATUS = {"ok": "✅", "warn": "⚠️ ", "info": "ℹ️ "}


def run(source: str, oa: OAClient) -> None:
    for sale in stripe_client.extract(source):
        f = stripe_client.normalize(sale)
        who = "business" if f["customer_vat_id"] else "consumer"
        tax = "on" if f["stripe_tax_enabled"] else "off"
        print(f"\n🧾  {f['seller_name']} ({f['seller_country']}) → {who} in {f['customer_country']} · "
              f"{f['currency']} {f['net']:.2f} · {f['product_type']} · Stripe Tax: {tax}")

        plan = oa.start("Check VAT place of supply on a sale", f["seller_country"] or "EU")
        slug = (plan.get("skills_to_load") or [None])[0]
        skill = oa.get_skill(slug) if slug else {}

        v = vat_check.check(f, skill)
        trust = f"tier {v.get('tier')}" + (f", signed off by {v['verifier']}" if v.get("verifier") else "")
        print(f"    OpenAccountants → {v.get('oa_skill_name') or 'VAT rules'}  ({trust})")
        print(f"    {STATUS.get(v['status'], '')} {v['headline']}")
        print(f"       {v['detail']}")
        if v.get("action"):
            print(f"       → {v['action']}")


def main(argv: list[str]) -> int:
    oa = OAClient()
    mode = "LIVE" if oa.live else "MOCK (set OA_MCP_TOKEN + STRIPE_API_KEY to go live)"
    print(f"Stripe → OpenAccountants · VAT place-of-supply demo  [{mode}]")
    here = os.path.dirname(os.path.abspath(__file__))
    source = argv[1] if len(argv) > 1 else os.path.join(here, "samples", "sales.json")
    run(source, oa)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
