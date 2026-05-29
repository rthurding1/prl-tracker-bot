"""$PRL Tracker Telegram bot.

Polls CoinGecko + Bitget on an interval, pushes alerts when FDV crosses a
$25M increment (cooldown-limited), and answers on-demand /status requests.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import alerts
import config
import storage
from market import fetch_snapshot

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("prl-bot")

HELP_TEXT = (
    "🪼 *$PRL Tracker*\n\n"
    "/status (or /prl) — current price, FDV, OI & short/long bias\n"
    "/subscribe — get auto-alerts when FDV crosses a "
    f"${config.FDV_INCREMENT // 1_000_000}M increment\n"
    "/unsubscribe — stop auto-alerts here\n"
    "/settings — show current alert settings\n"
    "/help — this message"
)


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)


async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("Fetching $PRL…")
    try:
        snap = await fetch_snapshot()
        await msg.edit_text(alerts.format_card(snap), parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:  # noqa: BLE001 - surface to user
        log.exception("status failed")
        await msg.edit_text(f"⚠️ Couldn't fetch data right now: {exc}")


async def subscribe_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    added = storage.add_subscriber(update.effective_chat.id)
    await update.message.reply_text(
        "✅ Subscribed to FDV alerts." if added else "You're already subscribed."
    )


async def unsubscribe_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    removed = storage.remove_subscriber(update.effective_chat.id)
    await update.message.reply_text(
        "🔕 Unsubscribed." if removed else "You weren't subscribed."
    )


async def settings_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state = storage.load()
    bucket = state.get("last_bucket")
    bucket_txt = (
        alerts._money(float(bucket * config.FDV_INCREMENT), 0) if bucket is not None else "n/a"
    )
    text = (
        "*Settings*\n"
        f"FDV increment: ${config.FDV_INCREMENT // 1_000_000}M\n"
        f"Cooldown: {config.COOLDOWN_SECONDS // 60} min\n"
        f"Poll interval: {config.POLL_INTERVAL_SECONDS}s\n"
        f"Subscribers: {len(state.get('subscribers', []))}\n"
        f"Last FDV bucket floor: {bucket_txt}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def poll_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job: fetch snapshot, evaluate FDV crossing, broadcast alerts."""
    try:
        snap = await fetch_snapshot()
    except Exception:
        log.exception("poll: snapshot fetch failed")
        return

    state = storage.load()
    message = alerts.evaluate(snap, state, now=time.time())
    storage.save(state)

    if not message:
        return

    subscribers = state.get("subscribers", [])
    if not subscribers:
        log.info("FDV crossing detected but no subscribers")
        return

    for chat_id in list(subscribers):
        try:
            await ctx.bot.send_message(
                chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            log.exception("failed to send alert to %s", chat_id)


def _start_keepalive_server() -> None:
    """Bind ``$PORT`` with a trivial HTTP server.

    Render's free web tier requires an open port and spins the service down
    after ~15 min without inbound traffic. Pointing a free uptime pinger
    (UptimeRobot / cron-job.org) at this endpoint every ~10 min keeps the poll
    loop alive. No-op locally when ``$PORT`` is unset.
    """
    port = os.getenv("PORT")
    if not port:
        return

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def do_HEAD(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):  # silence access logs
            pass

    srv = HTTPServer(("0.0.0.0", int(port)), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log.info("Keepalive HTTP server listening on :%s", port)


async def _on_startup(app: Application) -> None:
    # Auto-subscribe any chat ids provided via env, so you get alerts out of the box.
    for raw in config.DEFAULT_CHAT_IDS:
        try:
            storage.add_subscriber(int(raw))
        except ValueError:
            log.warning("Ignoring invalid TELEGRAM_CHAT_ID: %r", raw)


def main() -> None:
    config.validate()
    # PTB's run_polling relies on a current event loop existing in the main
    # thread; Python 3.12+ no longer auto-creates one, so ensure it here.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    _start_keepalive_server()
    app = Application.builder().token(config.BOT_TOKEN).post_init(_on_startup).build()

    app.add_handler(CommandHandler(["start", "help"], start_cmd))
    app.add_handler(CommandHandler(["status", "prl"], status_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))

    app.job_queue.run_repeating(
        poll_job, interval=config.POLL_INTERVAL_SECONDS, first=5
    )

    log.info("Starting $PRL tracker bot (poll every %ss)", config.POLL_INTERVAL_SECONDS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
