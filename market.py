"""Combine CoinGecko price/FDV with multi-exchange perp data."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

import config
from data import coingecko, perps
from data.perps import ExchangePerp


@dataclass
class Snapshot:
    cg: coingecko.CoinGeckoData
    perps: list[ExchangePerp]

    @property
    def fdv(self) -> float | None:
        return self.cg.fdv_usd

    @property
    def available_perps(self) -> list[ExchangePerp]:
        return [p for p in self.perps if p.available]

    @property
    def total_oi_usd(self) -> float | None:
        avail = self.available_perps
        return sum(p.oi_usd for p in avail) if avail else None

    @property
    def bias(self) -> tuple[str, str, float | None, float | None]:
        """Aggregate short/long bias across exchanges.

        Returns (emoji, label, long_pct, short_pct). Long/short account ratios
        are averaged over the exchanges that publish them; funding sign is the
        fallback when none do.
        """
        ratios = [
            (p.long_ratio, p.short_ratio)
            for p in self.perps
            if p.long_ratio is not None and p.short_ratio is not None
        ]
        if ratios:
            long_avg = sum(r[0] for r in ratios) / len(ratios)
            short_avg = sum(r[1] for r in ratios) / len(ratios)
            if long_avg - short_avg > 0.04:
                return "🟢", "Long bias", long_avg, short_avg
            if short_avg - long_avg > 0.04:
                return "🔴", "Short bias", long_avg, short_avg
            return "⚪", "Balanced", long_avg, short_avg

        # Fall back to OI-weighted funding sign.
        f = self.weighted_funding
        if f is not None:
            if f > 0:
                return "🟢", "Long bias (funding)", None, None
            if f < 0:
                return "🔴", "Short bias (funding)", None, None
        return "⚪", "Unknown", None, None

    @property
    def weighted_funding(self) -> float | None:
        """OI-weighted average funding rate across available exchanges."""
        pairs = [
            (p.oi_usd, p.funding_rate)
            for p in self.perps
            if p.funding_rate is not None and p.oi_usd is not None
        ]
        total_w = sum(w for w, _ in pairs)
        if not pairs or total_w == 0:
            return None
        return sum(w * fr for w, fr in pairs) / total_w


async def fetch_snapshot() -> Snapshot:
    async with httpx.AsyncClient(headers={"User-Agent": "prl-tracker-bot"}) as client:
        cg_task = coingecko.fetch(client, config.COINGECKO_ID)
        perps_task = perps.fetch_all(
            client,
            binance_symbol=config.BINANCE_SYMBOL,
            bybit_symbol=config.BYBIT_SYMBOL,
            bitget_symbol=config.BITGET_SYMBOL,
            bitget_product_type=config.BITGET_PRODUCT_TYPE,
        )
        cg_data, perp_list = await asyncio.gather(cg_task, perps_task)
    return Snapshot(cg=cg_data, perps=perp_list)
