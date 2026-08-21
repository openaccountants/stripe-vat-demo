"""Tests for Stripe VAT place-of-supply demo."""

import unittest
from oa_client import OAClient
import vat_check
import stripe_client


class StripeVATDemoTests(unittest.TestCase):
    def setUp(self):
        self.oa = OAClient(token=None)
        self.plan = self.oa.start("Determine VAT place of supply on sale", "MT")
        slug = (self.plan.get("skills_to_load") or [None])[0]
        self.skill = self.oa.get_skill(slug)

    def test_mock_oa_client(self):
        self.assertEqual(self.plan["jurisdiction"], "MT")
        self.assertEqual(self.skill["tier"], 1)
        self.assertIn("Michael Cutajar", self.skill["verifier"])

    def test_domestic_sale(self):
        facts = {
            "seller_country": "MT",
            "customer_country": "MT",
            "tax_charged": 17.82,
            "tax_rate": 0.18,
            "customer_vat_id": None,
            "product_type": "digital",
            "currency": "EUR",
            "stripe_tax_enabled": True,
        }
        res = vat_check.check(facts, self.skill)
        self.assertEqual(res["status"], "ok")
        self.assertIn("Correct domestic VAT", res["headline"])

    def test_intra_eu_b2b_reverse_charge(self):
        facts = {
            "seller_country": "MT",
            "customer_country": "DE",
            "tax_charged": 0.0,
            "tax_rate": 0.0,
            "customer_vat_id": "DE811569869",
            "product_type": "saas",
            "currency": "EUR",
            "stripe_tax_enabled": True,
        }
        res = vat_check.check(facts, self.skill)
        self.assertEqual(res["status"], "ok")
        self.assertIn("Reverse charge correctly applied", res["headline"])

    def test_intra_eu_b2b_wrong_vat_charged(self):
        facts = {
            "seller_country": "MT",
            "customer_country": "DE",
            "tax_charged": 228.0,
            "tax_rate": 0.19,
            "customer_vat_id": "DE811569869",
            "product_type": "saas",
            "currency": "EUR",
            "stripe_tax_enabled": False,
        }
        res = vat_check.check(facts, self.skill)
        self.assertEqual(res["status"], "warn")
        self.assertIn("VAT charged in error", res["headline"])

    def test_intra_eu_b2c_oss_undercharged(self):
        facts = {
            "seller_country": "MT",
            "customer_country": "FR",
            "tax_charged": 0.0,
            "tax_rate": 0.0,
            "customer_vat_id": None,
            "product_type": "digital",
            "currency": "EUR",
            "stripe_tax_enabled": False,
        }
        res = vat_check.check(facts, self.skill)
        self.assertEqual(res["status"], "warn")
        self.assertIn("Under-charged VAT", res["headline"])

    def test_samples_extraction(self):
        charges = stripe_client.extract("samples/sales.json")
        self.assertEqual(len(charges), 5)
        norm = stripe_client.normalize(charges[0])
        self.assertEqual(norm["seller_country"], "MT")
        self.assertEqual(norm["customer_country"], "FR")


if __name__ == "__main__":
    unittest.main()
