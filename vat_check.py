"""Apply the loaded OpenAccountants place-of-supply rules to a Stripe sale.

Covers the cases that matter for a digital/SaaS seller:
  - domestic        -> seller-country standard rate
  - intra-EU B2B    -> reverse charge (supplier 0%, customer self-accounts)
  - intra-EU B2C digital -> OSS: VAT at the CONSUMER's country rate (place of
    supply is the customer's country), not the seller's
  - non-EU customer -> outside EU VAT scope (flag local rules / Stripe Tax gap)

DELIBERATE SIMPLIFICATION (goods distance-selling thresholds, exemptions, etc.
omitted). Production leans on the full OA skill + an agent step; the named-CPA
sign-off is what makes the verdict relianceable.
"""

from __future__ import annotations

EU = {"AT","BE","BG","HR","CY","CZ","DE","DK","EE","ES","FI","FR","GR","HU","IE",
      "IT","LT","LU","LV","MT","NL","PL","PT","RO","SE","SI","SK"}


def check(facts: dict, oa_skill: dict) -> dict:
    rules = oa_skill.get("rules", {})
    rates = rules.get("standard_rates", {})
    base = {"oa_skill": oa_skill.get("slug"), "oa_skill_name": oa_skill.get("name"),
            "tier": oa_skill.get("tier"), "verifier": oa_skill.get("verifier"),
            "source": oa_skill.get("source")}

    sc, cc = facts["seller_country"], facts["customer_country"]
    charged, rate = facts["tax_charged"], facts["tax_rate"]
    is_b2b = bool(facts.get("customer_vat_id"))
    digital = facts["product_type"] in ("digital", "saas", "service", "electronic")
    off = "  (Stripe automatic tax was off.)" if not facts.get("stripe_tax_enabled") else ""

    def warn(headline, detail, action=None):
        return {**base, "status": "warn", "headline": headline, "detail": detail + off, "action": action}

    def ok(headline, detail):
        return {**base, "status": "ok", "headline": headline, "detail": detail}

    # Domestic
    if sc and cc and sc == cc:
        exp = rates.get(sc)
        if exp is None:
            return {**base, "status": "info", "headline": "Domestic sale — standard rate applies",
                    "detail": "Standard rate not confirmed from the loaded skill.", "action": None}
        if abs(rate - exp) < 0.005:
            return ok(f"Correct domestic VAT ({exp:.0%})", f"{sc} domestic sale at the verified standard rate {exp:.0%}.")
        return warn(f"VAT rate looks wrong ({rate:.0%} vs {exp:.0%})",
                    f"Charged {rate:.0%}; verified {sc} standard rate is {exp:.0%}.")

    # Intra-EU B2B -> reverse charge
    if sc in EU and cc in EU and sc != cc and is_b2b:
        if charged > 0.005:
            return warn("VAT charged in error — should be reverse charge",
                        f"Intra-EU B2B ({sc}→{cc}, VAT ID {facts['customer_vat_id']}): supplier invoices 0%, customer self-accounts. {facts['currency']} {charged:.2f} was charged.",
                        "credit the VAT; issue with a reverse-charge note")
        return ok("Reverse charge correctly applied", f"Intra-EU B2B ({sc}→{cc}): 0% VAT, customer self-accounts.")

    # Intra-EU B2C digital -> OSS, customer's country rate
    if sc in EU and cc in EU and sc != cc and not is_b2b and digital:
        exp = rates.get(cc)
        if exp is None:
            return {**base, "status": "info", "headline": "B2C digital — OSS applies",
                    "detail": f"Place of supply is the consumer's country ({cc}); rate not confirmed from the skill.", "action": None}
        if abs(rate - exp) < 0.005:
            return ok(f"Correct OSS VAT ({cc} {exp:.0%})", f"B2C digital to {cc}: VAT correctly charged at the consumer's-country rate under OSS.")
        delta = "Under-charged" if rate < exp else "Over-charged"
        return warn(f"{delta} VAT — B2C digital to {cc}: {exp:.0%} due (OSS), {rate:.0%} charged",
                    f"Place of supply for B2C electronically-supplied services is the consumer's country ({cc}); VAT is due via OSS at {exp:.0%}.",
                    f"register/report {cc} VAT via OSS — Stripe Tax does nothing here unless OSS-registered")

    # Non-EU customer
    if sc in EU and cc and cc not in EU:
        return {**base, "status": "info", "headline": f"Customer outside the EU ({cc}) — outside EU VAT scope",
                "detail": f"No EU VAT on this supply; check {cc} local rules (US sales-tax nexus, etc.). Stripe Tax may not cover {cc}.",
                "action": None}

    return {**base, "status": "info", "headline": "Scenario outside this demo's rule set",
            "detail": f"{sc or '?'}→{cc or '?'}, {'B2B' if is_b2b else 'B2C'}, {facts['product_type']} — needs the full OA skill / an agent step.",
            "action": None}
