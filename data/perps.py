"""Per-exchange perpetual data (OI, funding, long/short bias).

Fetches the PRL perp from Binance, Bybit and Bitget. Every fetcher degrades to
``None`` on failure rather than raising, so one exchange being down never breaks
the combined snapshot.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx


def _f(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


@dataclass
class ExchangePerp:
    name: str
    oi_base: float | None = None          # open interest in PRL units
    mark_price: float | None = None
    funding_rate: float | None = None     # per funding interval, e.g. -0.000438
    long_ratio: float | None = None       # account long ratio 0..1
    short_ratio: float | None = None      # account short ratio 0..1
    _oi_usd_direct: float | None = None   # set when the exchange reports USD OI

    @property
    def oi_usd(self) -> float | None:
        if self._oi_usd_direct is not None:
            return self._oi_usd_direct
        if self.oi_base is not None and self.mark_price is not None:
            return self.oi_base * self.mark_price
        return None

    @property
    def available(self) -> bool:
        return self.oi_usd is not None


async def _json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict | list:
    resp = await client.get(url, params=params, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


# ---------- Binance USDT-M futures ----------

async def fetch_binance(client: httpx.AsyncClient, symbol: str) -> ExchangePerp:
    p = ExchangePerp(name="Binance")
    try:
        oi = await _json(client, "https://fapi.binance.com/fapi/v1/openInterest", {"symbol": symbol})
        p.oi_base = _f(oi.get("openInterest"))
    except Exception:
        pass
    try:
        pi = await _json(client, "https://fapi.binance.com/fapi/v1/premiumIndex", {"symbol": symbol})
        row = pi[0] if isinstance(pi, list) and pi else pi
        p.mark_price = _f(row.get("markPrice"))
        p.funding_rate = _f(row.get("lastFundingRate"))
    except Exception:
        pass
    try:
        ls = await _json(
            client,
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            {"symbol": symbol, "period": "1h", "limit": 1},
        )
        if isinstance(ls, list) and ls:
            p.long_ratio = _f(ls[-1].get("longAccount"))
            p.short_ratio = _f(ls[-1].get("shortAccount"))
    except Exception:
        pass
    return p


# ---------- Bybit linear perps ----------

async def fetch_bybit(client: httpx.AsyncClient, symbol: str) -> ExchangePerp:
    p = ExchangePerp(name="Bybit")
    try:
        data = await _json(
            client,
            "https://api.bybit.com/v5/market/tickers",
            {"category": "linear", "symbol": symbol},
        )
        rows = (data.get("result") or {}).get("list") or []
        if rows:
            row = rows[0]
            p.oi_base = _f(row.get("openInterest"))
            p._oi_usd_direct = _f(row.get("openInterestValue"))
            p.mark_price = _f(row.get("markPrice"))
            p.funding_rate = _f(row.get("fundingRate"))
    except Exception:
        pass
    return p


# ---------- Bitget USDT-M futures ----------

_BITGET = "https://api.bitget.com/api/v2/mix/market"


async def _bitget_get(client: httpx.AsyncClient, path: str, params: dict):
    body = await _json(client, f"{_BITGET}/{path}", params)
    if str(body.get("code")) != "00000":
        raise RuntimeError(body.get("msg"))
    return body.get("data")


async def fetch_bitget(client: httpx.AsyncClient, symbol: str, product_type: str) -> ExchangePerp:
    p = ExchangePerp(name="Bitget")
    base = {"symbol": symbol, "productType": product_type}
    try:
        data = await _bitget_get(client, "open-interest", base)
        lst = (data or {}).get("openInterestList") or []
        if lst:
            p.oi_base = _f(lst[0].get("size"))
    except Exception:
        pass
    try:
        data = await _bitget_get(client, "ticker", base)
        row = data[0] if isinstance(data, list) and data else data
        if row:
            p.mark_price = _f(row.get("markPrice"))
    except Exception:
        pass
    try:
        data = await _bitget_get(client, "current-fund-rate", base)
        row = data[0] if isinstance(data, list) and data else data
        if row:
            p.funding_rate = _f(row.get("fundingRate"))
    except Exception:
        pass
    try:
        data = await _bitget_get(client, "account-long-short", {**base, "period": "1h"})
        rows = data if isinstance(data, list) else (data or {}).get("list") or []
        if rows:
            p.long_ratio = _f(rows[-1].get("longAccountRatio"))
            p.short_ratio = _f(rows[-1].get("shortAccountRatio"))
    except Exception:
        pass
    return p


async def fetch_all(
    client: httpx.AsyncClient,
    binance_symbol: str,
    bybit_symbol: str,
    bitget_symbol: str,
    bitget_product_type: str,
) -> list[ExchangePerp]:
    return list(
        await asyncio.gather(
            fetch_binance(client, binance_symbol),
            fetch_bybit(client, bybit_symbol),
            fetch_bitget(client, bitget_symbol, bitget_product_type),
        )
    )
