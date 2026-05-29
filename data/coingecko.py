"""CoinGecko price / FDV fetcher (free, no API key)."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

BASE = "https://api.coingecko.com/api/v3"


@dataclass
class CoinGeckoData:
    price_usd: float | None
    fdv_usd: float | None
    market_cap_usd: float | None
    volume_24h_usd: float | None
    change_24h_pct: float | None


async def fetch(client: httpx.AsyncClient, coin_id: str) -> CoinGeckoData:
    """Fetch market data for a coin. Raises httpx errors on failure."""
    url = f"{BASE}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false",
    }
    resp = await client.get(url, params=params, timeout=15.0)
    resp.raise_for_status()
    md = resp.json().get("market_data", {}) or {}

    def _usd(field: str) -> float | None:
        val = md.get(field)
        if isinstance(val, dict):
            return val.get("usd")
        return val

    return CoinGeckoData(
        price_usd=_usd("current_price"),
        fdv_usd=_usd("fully_diluted_valuation"),
        market_cap_usd=_usd("market_cap"),
        volume_24h_usd=_usd("total_volume"),
        change_24h_pct=md.get("price_change_percentage_24h"),
    )
