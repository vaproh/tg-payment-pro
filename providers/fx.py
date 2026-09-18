import time
import logging
import requests

import config

logger = logging.getLogger(__name__)

_cache = {"rate": 0.0, "ts": 0.0, "src": ""}
CACHE_TTL = 600
FALLBACK_RATE = 83.0

PROVIDERS = [
    ("er-api", "https://open.er-api.com/v6/latest/USD", lambda j: float(j["rates"]["INR"])),
    ("frankfurter", "https://api.frankfurter.app/latest?from=USD&to=INR", lambda j: float(j["rates"]["INR"])),
]


def _fetch_live():
    last_err = None
    for name, url, parse in PROVIDERS:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return parse(r.json()), name
        except Exception as e:
            last_err = e
            logger.warning("FX provider %s failed: %s", name, e)
    raise RuntimeError(f"all FX providers failed: {last_err}")


def get_inr_per_usd():
    """INR per 1 USD. Env override wins, else cached fetch, else fallback."""
    if config.INR_PER_USD_OVERRIDE:
        try:
            return float(config.INR_PER_USD_OVERRIDE), "override", 0
        except ValueError:
            pass
    now = time.time()
    if _cache["rate"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["rate"], f"cache({_cache['src']})", int(CACHE_TTL - (now - _cache["ts"]))
    try:
        rate, name = _fetch_live()
        _cache.update({"rate": rate, "ts": now, "src": name})
        return rate, f"live({name})", 0
    except Exception as e:
        logger.warning("FX fetch failed: %s", e)
        if _cache["rate"]:
            return _cache["rate"], f"stale-cache({_cache['src']})", 0
        return FALLBACK_RATE, "fallback", 0


def inr_to_usd(amount_inr):
    rate, src, _ = get_inr_per_usd()
    return round(float(amount_inr) / rate, 2), rate, src


def usd_to_inr(amount_usd):
    rate, src, _ = get_inr_per_usd()
    return round(float(amount_usd) * rate, 0), rate, src
