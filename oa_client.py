"""OpenAccountants MCP client.

JSON-RPC 2.0 to https://www.openaccountants.com/api/mcp. The MCP requires auth on
tool calls (OA_MCP_TOKEN) for live mode; without one it returns bundled sample
responses that mirror the live shape so the demo runs end to end.

  - start(intent, jurisdiction)  -> which verified skill governs the question
  - get_skill(slug)              -> place-of-supply rules + tier + named verifier
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

MCP_URL = os.environ.get("OA_MCP_URL", "https://www.openaccountants.com/api/mcp")
MCP_TOKEN = os.environ.get("OA_MCP_TOKEN")


class OAClient:
    def __init__(self, token: str | None = MCP_TOKEN, url: str = MCP_URL):
        self.token, self.url, self._id = token, url, 0

    @property
    def live(self) -> bool:
        return bool(self.token)

    def start(self, intent: str, jurisdiction: str) -> dict:
        if not self.live:
            return _MOCK_START.get(jurisdiction.upper(), _MOCK_START["_DEFAULT"])
        return self._call("start", {"intent": intent, "jurisdiction": jurisdiction})

    def get_skill(self, slug: str) -> dict:
        if not self.live:
            return _MOCK_SKILL.get(slug, _MOCK_SKILL["_DEFAULT"])
        return self._call("get_skill", {"slug": slug})

    def _call(self, tool: str, arguments: dict) -> dict:
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments}}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"  # scheme TBD; swap if OA uses apikey
        req = urllib.request.Request(self.url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"OA MCP HTTP {e.code}: {e.read().decode()[:300]}") from e
        if "error" in payload and payload["error"]:
            raise RuntimeError(f"OA MCP error: {payload['error']}")
        result = payload.get("result", {})
        if isinstance(result.get("structuredContent"), (dict, list)):
            return result["structuredContent"]
        return json.loads((result.get("content") or [{}])[0].get("text", "{}"))


# --- Bundled sample responses (mirror live MCP shape) ----------------------
# Seller is Malta, so the verifier is the real MT jurisdiction lead. Live, every
# field comes from get_skill.

_MOCK_START = {
    "MT": {"jurisdiction": "MT", "skills_to_load": ["mt-vat-place-of-supply"],
           "next_action": "Load the skill, then check each sale's place of supply."},
    "_DEFAULT": {"jurisdiction": "EU", "skills_to_load": ["mt-vat-place-of-supply"],
                 "next_action": "Load the skill, then check each sale's place of supply."},
}

_MOCK_SKILL = {
    "mt-vat-place-of-supply": {
        "slug": "mt-vat-place-of-supply",
        "name": "Malta — VAT place of supply (incl. OSS for B2C digital)",
        "jurisdiction": "MT", "tier": 1, "verifier": "Michael Cutajar, CPA (Malta)",
        "rules": {
            # EU standard VAT rates (illustrative — production reads them from the skill).
            "standard_rates": {"MT": 0.18, "FR": 0.20, "DE": 0.19, "IE": 0.23, "ES": 0.21, "IT": 0.22, "NL": 0.21},
            "b2b_intra_eu": "reverse_charge",          # supplier invoices 0%, customer self-accounts
            "b2c_digital_intra_eu": "customer_country", # OSS: VAT at the consumer's country rate
        },
        "source": "https://www.openaccountants.com/skills/mt-vat-place-of-supply",
    },
    "_DEFAULT": {"slug": "eu-vat-place-of-supply", "name": "EU — VAT place of supply",
                 "jurisdiction": "EU", "tier": 2, "verifier": None,
                 "rules": {"standard_rates": {}, "b2b_intra_eu": "reverse_charge",
                           "b2c_digital_intra_eu": "customer_country"},
                 "source": "https://www.openaccountants.com/skills"},
}
