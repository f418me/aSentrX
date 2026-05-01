# aSentrX

Automated Bitcoin trading system that monitors high-impact news sources in real time and executes trades on Bitfinex based on AI analysis.

## How It Works

aSentrX watches two signal sources simultaneously:

1. **Donald Trump's Truth Social posts** — via WebSocket streaming
2. **Federal Reserve FOMC press releases** — via periodic web scraping

When a new signal arrives, an AI agent analyzes the content and predicts the likely impact on Bitcoin. If the confidence score clears a configurable threshold, a leveraged LIMIT order is placed on the Bitfinex perpetual futures market (`tBTCF0:USTF0`).

## System Architecture

```
┌─────────────────────────────┐    ┌──────────────────────────────┐
│  asentrx-truthsocial-monitor│    │     asentrx-web-monitor      │
│  (Node.js, runs locally)    │    │  (Python, Fly.io · arn)      │
│                             │    │                              │
│  WebSocket stream from      │    │  Polls FED FOMC press-       │
│  truthsocial.com → filters  │    │  release index, extracts     │
│  for Trump's account ID     │    │  article text                │
└────────────┬────────────────┘    └──────────────┬───────────────┘
             │ POST /notify/truth-social           │ POST /notify/web-monitor
             └──────────────────┬─────────────────┘
                                ▼
             ┌──────────────────────────────────────┐
             │     asentrx-trade-decision-engine    │
             │     (Python/FastAPI, Fly.io · lax)   │
             │                                      │
             │  Routes by payload type              │
             │  ├─ "truthsocial" → SocialMedia Agent│
             │  └─ "web-monitor" → FED Decision Agent│
             │                                      │
             │  Confidence gate → TradeDecisionManager
             │  └─ Bitfinex LIMIT order             │
             │  └─ SMS alert (Twilio)               │
             │  └─ Logs (Logfire + Sentry)          │
             └──────────────────────────────────────┘

             ┌──────────────────────────────────────┐
             │     asentrx-fly-orchestrator         │
             │     (Python, Fly.io · fra)           │
             │                                      │
             │  Starts/stops asentrx-web-monitor    │
             │  around scheduled FOMC event windows │
             └──────────────────────────────────────┘
```

## Services

### asentrx-truthsocial-monitor
Connects to Truth Social's Mastodon-compatible WebSocket streaming API and filters for posts from Trump's account (`@realDonaldTrump`, ID `107780257626128497`). On each new post it sends a structured payload to the trade-decision-engine and optionally to an additional webhook.

Runs **locally** (Node.js). OAuth tokens are extracted from a running Chrome instance and expire periodically.

→ [Repository](https://github.com/f418me/asentrx-truthsocial-monitor)

---

### asentrx-web-monitor
Polls the Federal Reserve FOMC press-release index page. When a new article whose title contains `fomc statement` appears, it fetches the full text and forwards it to the trade-decision-engine.

Includes cold-start protection (`MONITOR_BOOTSTRAP_SKIP_EXISTING=true`) to avoid replaying the most recent statement when the machine restarts.

Deployed on **Fly.io** (region: `arn` / Stockholm). Multiple instances can run in parallel for redundancy — the engine deduplicates by URL.

→ [Repository](https://github.com/f418me/asentrx-web-monitor)

---

### asentrx-trade-decision-engine
The central FastAPI service. Receives payloads from the monitors and routes them to the correct AI agent:

- **FED Decision Agent** — compares the actual rate decision and FOMC narrative against predefined expectations (`app/expectations.json`) and predicts the Bitcoin impact (positive / negative / neutral).
- **Social Media Agent** — two-stage pipeline: topic classification (market / bitcoin / tariffs / irrelevant) → price direction prediction.

Both agents return structured pydantic-ai outputs. `TradeDecisionManager` checks the confidence score against per-source, per-topic thresholds and executes a LIMIT order on Bitfinex if the threshold is met. A `PROD_EXECUTION=False` flag enables dry-run mode.

Deployed on **Fly.io** (region: `lax` / Los Angeles).

→ [Repository](https://github.com/f418me/asentrx-trade-decision-engine)

---

### asentrx-fly-orchestrator
Starts and stops the `asentrx-web-monitor` Fly.io machines at scheduled UTC times. Used to spin up the web monitor shortly before an expected FOMC press conference and shut it down after. Supports both recurring `HH:MM` schedules and one-time `YYYY-MM-DD HH:MM` datetimes.

Deployed on **Fly.io** (region: `fra` / Frankfurt).

→ [Repository](https://github.com/f418me/asentrx-fly-orchestrator)

---

## Payload Contracts

### Truth Social → Trade Engine (`POST /notify/truth-social`)
```json
{
  "type": "truthsocial",
  "url": "https://truthsocial.com/@realDonaldTrump/114589902466767844",
  "username": "realDonaldTrump",
  "content-id": "114589902466767844",
  "content": "The tariffs on China are now 200%...",
  "ip": "1.2.3.4"
}
```

### Web Monitor → Trade Engine (`POST /notify/web-monitor`)
```json
{
  "type": "web-monitor",
  "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260429a.htm",
  "content-id": "monetary20260429a",
  "content": "Full extracted article text...",
  "ip": "1.2.3.4"
}
```

## Configuration

### asentrx-truthsocial-monitor (`.env`)

| Variable | Required | Description |
|---|---|---|
| `ACCESS_TOKEN` | Yes | OAuth token — extracted via `npm run auth` |
| `TRADE_ENGINE_URL` | Yes | e.g. `https://asentrx-trade-decision-engine.fly.dev` |
| `WEBHOOK_URL` | No | Additional webhook endpoint |

### asentrx-web-monitor (`.env` / Fly secrets)

| Variable | Description |
|---|---|
| `WEBSERVICE_URL` | Full URL of the trade engine endpoint |
| `MONITOR_MODE` | `production` (randomized interval) or `normal` |
| `MONITOR_BOOTSTRAP_SKIP_EXISTING` | `true` to skip replay on cold start |

### asentrx-trade-decision-engine (`.env` / Fly secrets)

| Variable | Description |
|---|---|
| `PROD_EXECUTION` | `True` for live trading, `False` for dry-run |
| `MODEL` | LLM model string, e.g. `openai:gpt-5.4` |
| `OPENAI_API_KEY` | Required when using an OpenAI model |
| `BFX_API_KEY` / `BFX_API_SECRET` | Bitfinex API credentials |
| `CONFIDENCE_THRESHOLD_FED_HIGH/MED` | Gates for FED signal trading |
| `CONFIDENCE_THRESHOLD_BITCOIN_HIGH/MED` | Gates for social media signal trading |
| `ORDER_AMOUNT_FED_*` / `LEVERAGE_FED_*` | FED trade sizes and leverage |
| `ORDER_AMOUNT_BITCOIN_*` / `LEVERAGE_BITCOIN_*` | Social media trade sizes and leverage |
| `SMS_NOTIFICATIONS_ENABLED` | `True` to send Twilio SMS alerts |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Twilio credentials |
| `LOGFIRE_TOKEN` / `SENTRY_DSN` | Observability (optional) |

A full `.env-example` with all variables is included in the trade-decision-engine repository.

### asentrx-fly-orchestrator (`.env` / Fly secrets)

| Variable | Description |
|---|---|
| `FLY_API_TOKEN` | Fly.io personal access token |
| `FLY_APP_TO_ORCHESTRATE` | Name of the Fly.io app to start/stop |
| `START_TIME` / `SHUTDOWN_TIME` | Recurring UTC times (HH:MM) |
| `START_DATETIME` / `SHUTDOWN_DATETIME` | One-time UTC datetimes (YYYY-MM-DD HH:MM) |

## Local Development

**Trade Decision Engine:**
```bash
cd asentrx-trade-decision-engine
cp .env-example .env  # fill in credentials
poetry install
poetry run uvicorn app.main:app --reload
# API available at http://localhost:8000
```

**Truth Social Monitor** (requires Chrome with remote debugging):
```bash
# Start Chrome with remote debugging enabled
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp
# Log in to truthsocial.com in that Chrome window, then:
cd asentrx-truthsocial-monitor
npm install
npm run auth            # extracts and writes ACCESS_TOKEN to .env
echo "TRADE_ENGINE_URL=http://localhost:8000" >> .env
npm start
```

**Web Monitor:**
```bash
cd asentrx-web-monitor
poetry install
WEBSERVICE_URL=http://localhost:8000/notify/web-monitor python main.py
```

## Testing the Trade Engine

```bash
# Simulate a Truth Social post
curl -X POST http://localhost:8000/notify/truth-social \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "truthsocial",
    "url": "https://truthsocial.com/@realDonaldTrump/1",
    "username": "realDonaldTrump",
    "content-id": "test-001",
    "content": "We are doubling tariffs on China immediately. AMERICA FIRST!",
    "ip": "127.0.0.1"
  }'

# Simulate an FOMC announcement
curl -X POST http://localhost:8000/notify/web-monitor \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "web-monitor",
    "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260101a.htm",
    "content-id": "monetary20260101a",
    "content": "The FOMC decided to lower the target range for the federal funds rate by 25 basis points.",
    "ip": "127.0.0.1"
  }'
```

## Deployment (Fly.io)

Each service is deployed independently:

```bash
# Trade engine
cd asentrx-trade-decision-engine
fly deploy

# Web monitor
cd asentrx-web-monitor
fly deploy

# Orchestrator
cd asentrx-fly-orchestrator
fly deploy
```

Secrets (API keys, tokens) are set via `fly secrets set KEY=value` and are not stored in `fly.toml`.

## Important Operational Notes

- **Truth Social OAuth tokens expire.** Re-run `npm run auth` and restart the monitor when the stream stops delivering posts.
- **`PROD_EXECUTION=False` by default.** Set to `True` explicitly in the trade engine to enable live order placement.
- **Deduplication is in-memory.** Restarting the trade engine clears the processed content ID set. This is acceptable since Truth Social posts use unique IDs and FED articles use unique URLs.
- **`app/expectations.json`** must be present and up to date for the FED Decision Agent to function. It defines what rate decision and narrative was expected before an FOMC meeting.
