# 🪼 $PRL Tracker — Telegram Bot

Tracks the **Perle ($PRL)** token and pushes Telegram alerts whenever its
**fully-diluted valuation (FDV) crosses a $25M increment**, plus on-demand
snapshots of price, FDV, open interest and short/long bias.

## What it reports

- **Price** + 24h delta (CoinGecko)
- **FDV** + market cap + 24h volume (CoinGecko)
- **Combined open interest in USD** across **Binance + Bybit + Bitget**, with a per-exchange breakdown
- **Short/long bias** from averaged long/short account ratios (Binance + Bitget), with OI-weighted funding rate
- All data sources are **free, no API keys required**

## Commands

| Command | Description |
| --- | --- |
| `/status` (or `/prl`) | Current snapshot card |
| `/subscribe` | Receive auto FDV-crossing alerts in this chat |
| `/unsubscribe` | Stop alerts in this chat |
| `/settings` | Show increment, cooldown, poll interval |
| `/help` | Command list |

## Alert rule

On every poll the bot computes `bucket = floor(FDV / $25M)`. When the bucket
changes (FDV crossed a $25M boundary **up or down**) it sends an alert — but no
more than once per **1-hour cooldown**, so a price ranging on a boundary won't
spam you. Both the increment and cooldown are configurable via env vars.

## Local setup

```bash
cd prl-tracker-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set TELEGRAM_BOT_TOKEN (from @BotFather)
# optionally set TELEGRAM_CHAT_ID (from @userinfobot) to auto-subscribe yourself

python bot.py
```

Then message your bot `/status` in Telegram.

## Testing the alert

1. `/subscribe` in your chat.
2. In `.env` set `FDV_INCREMENT=1_000_000` (small) and restart the bot.
3. Within ~60s you should receive an FDV-crossing alert as PRL's FDV moves
   across a $1M boundary.
4. Revert `FDV_INCREMENT=25_000_000`.

## Deploy on Render (free, no credit card)

Render's free tier has no worker type and **spins a service down after ~15 min
without inbound HTTP traffic**. The bot handles this: when `$PORT` is set it
starts a tiny keepalive HTTP server, and you point a free uptime pinger at it to
stay awake. `render.yaml` is included.

1. Push this folder to a GitHub repo.
2. On [render.com](https://render.com) → **New → Web Service** → connect the repo.
   Render reads `render.yaml`: runtime Python, build `pip install -r requirements.txt`,
   start `python bot.py`, plan **free**.
3. Set env vars: `TELEGRAM_BOT_TOKEN` (and optionally `TELEGRAM_CHAT_ID`).
   Render injects `PORT` automatically → the keepalive server binds it.
4. Deploy. Logs should show `Keepalive HTTP server listening on :<port>` and
   `Starting $PRL tracker bot`. Copy the service URL (e.g. `https://prl-tracker-bot.onrender.com`).
5. **Keep it awake:** create a free monitor at [UptimeRobot](https://uptimerobot.com)
   or [cron-job.org](https://cron-job.org) that GETs that URL every **10 minutes**.
6. Send `/status` in Telegram to confirm.

> Note: `state.json` (subscribers + alert state) lives on local disk and resets
> on redeploy. Set `TELEGRAM_CHAT_ID` so you're auto-subscribed on every startup.

## Files

| File | Role |
| --- | --- |
| `bot.py` | Entrypoint: handlers, poll job, keepalive server |
| `config.py` | Env config |
| `market.py` | Combines sources into a `Snapshot`, aggregates OI + bias |
| `data/coingecko.py` | Price / FDV |
| `data/perps.py` | Per-exchange OI / funding / long-short (Binance, Bybit, Bitget) |
| `alerts.py` | FDV crossing detection + message formatting |
| `storage.py` | JSON persistence |
| `render.yaml` | Render free web-service blueprint |
