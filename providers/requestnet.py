"""Request Network Secure Payments (crypto, USD). Docs: POST /v2/secure-payments."""
import logging
import requests

import config

logger = logging.getLogger(__name__)
API = "https://api.request.network/v2/secure-payments"


def create_crypto_link(link_id, amount_usd, creator=""):
    body = {
        "requests": [{"amount": str(amount_usd)}],
        "reference": link_id,
        "payerIdentifier": str(creator or link_id),
    }
    if config.RN_DESTINATION_ID:
        # destinationId = "<interopAddr>:<tokenAddress>"
        body["requests"][0]["destinationId"] = config.RN_DESTINATION_ID
    r = requests.post(
        API,
        headers={"Content-Type": "application/json", "x-client-id": config.RN_CLIENT_ID},
        json=body,
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "url": data["securePaymentUrl"],
        "provider_ref": ",".join(data.get("requestIds", [])),
        "token": data.get("token", ""),
    }
