"""FDV-crossing detection and Telegram message formatting."""
from __future__ import annotations

import math

import config
from market import Snapshot


# ---------- formatting helpers ----------

def _money(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "n/a"
    a = abs(val)
    if a >= 1_000_000_000:
        return f"${val / 1_000_000_000:.{decimals}f}B"
    if a >= 1_000_000:
        return f"${val / 1_000_000:.{decimals}f}M"
    if a >= 1_000:
        return f"${val / 1_000:.{decimals}f}K"
    return f"${val:,.2f}"


def _price(val: float | None) -> str:
    if val is None:
        return "n/a"
    return f"${val:,.4f}" if val < 1 else f"${val:,.2f}"


def _pct(val: float | None) -> str:
    if val is None:
        return "n/a"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


def format_card(snap: Snapshot, header: str | None = None) -> str:
    cg = snap.cg
    emoji, bias_label, long_pct, short_pct = snap.bias
    total_oi = snap.total_oi_usd

    lines: list[str] = []
    if header:
        lines.append(header)
    lines.append("🪼 *$PRL — Perle*")
    lines.append(f"Price: {_price(cg.price_usd)}  (24h {_pct(cg.change_24h_pct)})")
    lines.append(f"FDV:   {_money(cg.fdv_usd)}   |  MCap: {_money(cg.market_cap_usd)}")
    lines.append("─────────────")
    lines.append(f"OI total: {_money(total_oi)}")
    for p in snap.perps:
        if p.oi_usd is None:
            lines.append(f"  • {p.name}: n/a")
        else:
            share = f" ({p.oi_usd / total_oi * 100:.0f}%)" if total_oi else ""
            lines.append(f"  • {p.name}: {_money(p.oi_usd)}{share}")

    ratio = ""
    if long_pct is not None and short_pct is not None:
        ratio = f"  (L {long_pct * 100:.0f}% / S {short_pct * 100:.0f}%)"
    lines.append(f"Bias:  {emoji} {bias_label}{ratio}")

    funding = snap.weighted_funding
    if funding is not None:
        lines.append(f"Funding: {funding * 100:.4f}% (avg)")
    lines.append(f"Vol 24h: {_money(cg.volume_24h_usd)}")
    return "\n".join(lines)


# ---------- FDV crossing logic ----------

def bucket_of(fdv: float) -> int:
    return math.floor(fdv / config.FDV_INCREMENT)


def milestone_message(snap: Snapshot, old_bucket: int, new_bucket: int) -> str:
    """Header line naming the milestone that was crossed."""
    direction = "up" if new_bucket > old_bucket else "down"
    arrow = "📈" if direction == "up" else "📉"
    # The boundary just crossed is the higher of the two buckets when going up,
    # and the boundary we dropped below when going down.
    boundary = (new_bucket if direction == "up" else old_bucket) * config.FDV_INCREMENT
    return f"{arrow} *FDV crossed {_money(float(boundary), 0)}* ({direction})\n"


def evaluate(snap: Snapshot, state: dict, now: float) -> str | None:
    """Decide whether to send an FDV alert.

    Mutates `state` (last_bucket / last_alert_ts) and returns a formatted alert
    message string when an alert should be sent, else None.
    """
    fdv = snap.fdv
    if fdv is None:
        return None

    new_bucket = bucket_of(fdv)
    last_bucket = state.get("last_bucket")

    # First observation: record baseline silently.
    if last_bucket is None:
        state["last_bucket"] = new_bucket
        return None

    if new_bucket == last_bucket:
        return None

    # Bucket changed -> a $25M boundary was crossed.
    last_alert_ts = state.get("last_alert_ts", 0) or 0
    within_cooldown = (now - last_alert_ts) < config.COOLDOWN_SECONDS

    header = milestone_message(snap, last_bucket, new_bucket)
    state["last_bucket"] = new_bucket  # always track current bucket

    if within_cooldown:
        return None

    state["last_alert_ts"] = now
    return format_card(snap, header=header)
