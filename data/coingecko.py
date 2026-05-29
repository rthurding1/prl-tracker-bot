"""CoinGecko price / FDV fetcher (free; optional demo API key)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

import config

log = logging.getLogger("prl-bot")

BASE = "https://api.coingecko.com/api/v3"


@dataclass
class CoinGeckoData:
    price_usd: float | None = None
    fdv_usd: float | None = None
    market_cap_usd: float | None = None
    volume_24h_usd: float | None = None
    change_24h_pct: float | None = None


async def fetch(client: httpx.AsyncClient, coin_id: str) -> CoinGeckoData:
    """Fetch market data. Never raises — returns empty data on failure so the
    rest of the snapshot (exchange OI) still renders. Retries once on 429."""
    url = f"{BASE}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false",
    }
    headers = {}
    if config.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = config.COINGECKO_API_KEY

    for attempt in range(2):
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=15.0)
            if resp.status_code == 429 and attempt == 0:
                await asyncio.sleep(3)
                continue
            resp.raise_for_status()
            md = resp.json().get("market_data", {}) or {}

            def _usd(field: str) -> float | None:
                val = md.get(field)
                return val.get("usd") if isinstance(val, dict) else val

            return CoinGeckoData(
                price_usd=_usd("current_price"),
                fdv_usd=_usd("fully_diluted_valuation"),
                market_cap_usd=_usd("market_cap"),
                volume_24h_usd=_usd("total_volume"),
                change_24h_pct=md.get("price_change_percentage_24h"),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("CoinGecko fetch failed (attempt %d): %s", attempt + 1, exc)

    return CoinGeckoData()
