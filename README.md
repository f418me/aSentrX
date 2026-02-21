# aSentrX

Automated social-signal trading bot for Truth Social with LLM-based analysis and optional Bitfinex execution.

`aSentrX` continuously fetches new posts, classifies relevance and expected market direction, and can place leveraged limit orders when confidence thresholds are met.

## Table of Contents
- [Overview aSentrX](#overview-asentrx)
- [Quickstart](#quickstart)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Run Locally](#run-locally)
- [Run with Docker](#run-with-docker)
- [Testing](#testing)
- [Deployment (Fly.io)](#deployment-flyio)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)
- [Contributing](#contributing)
- [License](#license)

## Overview aSentrX
- Monitors a target account on Truth Social via Playwright.
- Extracts and normalizes post content.
- Uses `pydantic-ai` + configurable LLM provider for trade decisions.
- Executes orders on Bitfinex when `PROD_EXECUTION=True`.
- Sends SMS notifications via Twilio.
- Emits structured logs/traces with Logfire.

## Quickstart

1. Clone and enter project:
```bash
git clone <your-repository-url>
cd aSentrX
```

2. Install dependencies (Python 3.13):
```bash
poetry install
```

3. Create env file:
```bash
cp .env_example .env
```

4. Set minimum required values in `.env`:
- `MODEL`
- One LLM API key matching your model (`OPENAI_API_KEY` or `GROQ_API_KEY` or `GEMINI_API_KEY`)
- `PROD_EXECUTION=False` (recommended until fully validated)

5. Install Playwright browser:
```bash
poetry run playwright install chromium
```

6. Start:
```bash
poetry run python main.py
```

## How It Works

High-level runtime flow:
1. Fetch latest statuses for `TARGET_USERNAME`.
2. Parse content and metadata.
3. Run LLM classification + direction/confidence scoring.
4. If configured thresholds are met, compute order parameters.
5. Submit Bitfinex order through the internal REST client.
6. Log outcome and send optional SMS notification.

Main entrypoint: `main.py`.

## Requirements
- Python `3.13+`
- Poetry `2.x`
- Optional: Docker (for containerized runtime)

## Configuration

Copy `.env_example` to `.env` and adjust values.

### Core Runtime
- `PROD_EXECUTION` (`False`/`True`): dry-run vs live trading
- `TARGET_USERNAME`: account to monitor (default: `realDonaldTrump`)
- `FETCH_INTERVAL_SECONDS`: polling interval
- `INITIAL_SINCE_ID`: optional bootstrap ID
- `PLAYWRIGHT_HEADLESS`: run browser headless

### LLM
- `MODEL` (examples):
  - `openai:gpt-4o`
  - `groq:llama-3.3-70b-versatile`
  - `google-gla:gemini-2.0-flash`
- Provide matching API key:
  - `OPENAI_API_KEY` or `GROQ_API_KEY` or `GEMINI_API_KEY`

### Bitfinex (required for live execution)
- `BFX_API_KEY`
- `BFX_API_SECRET`

### Risk/Order Settings
- `CONFIDENCE_THRESHOLD_HIGH`, `CONFIDENCE_THRESHOLD_MED`
- `ORDER_AMOUNT_*`
- `LEVERAGE_*`
- `LIMIT_OFFSET_BUY`, `LIMIT_OFFSET_SHORT`

### Observability / Notifications
- `LOG_LEVEL_CONSOLE`
- `LOGFIRE_TOKEN`, `LOGFIRE_ENVIRONMENT`, `LOGFIRE_SERVICE_NAME`
- `SMS_NOTIFICATIONS_ENABLED`
- `TWILIO_*`

### Optional Proxy (Decodo)
- `DECODO_PROXY_ENABLED`
- `DECODO_PROXY_URL`
- `DECODO_PROXY_USERNAME`, `DECODO_PROXY_PASSWORD`
- `DECODO_PROXY_MAX_RETRIES`

## Run Locally

Install deps and run:
```bash
poetry install
poetry run playwright install chromium
poetry run python main.py
```

## Run with Docker

Build image:
```bash
docker build -t asentrx:local .
```

Run container:
```bash
docker run --rm --name asentrx --env-file .env asentrx:local
```

Detached mode:
```bash
docker run -d --name asentrx --env-file .env asentrx:local
```

Logs:
```bash
docker logs -f asentrx
```

## Testing

Run tests:
```bash
poetry run pytest -q
```

Current baseline in this repo: tests pass with Python 3.13.

## Deployment (Fly.io)

- Configure app and secrets in Fly.io.
- Keep all sensitive env values in Fly secrets, not in repo files.

Example:
```bash
fly secrets set BFX_API_KEY="..." -a <fly-app-name>
fly secrets set BFX_API_SECRET="..." -a <fly-app-name>
```

## Troubleshooting

- `playwright: not found` in container:
  - Ensure binaries are copied before `playwright install` in Docker build.
- Poetry errors about config keys:
  - Use Poetry 2.x with this project.
- No trades executed:
  - Confirm `PROD_EXECUTION=True`, Bitfinex keys, and confidence thresholds.
- Truth Social fetch blocked:
  - Enable proxy + retries (`DECODO_PROXY_*`).

## Security Notes

- Never commit `.env`.
- Keep `PROD_EXECUTION=False` in development.
- Use restricted API keys (least privilege).
- Monitor and alert on failed/partial order flows.

## Contributing

1. Create a feature branch.
2. Keep changes small and focused.
3. Run tests locally.
4. Open PR with:
   - summary of changes
   - risk notes
   - validation steps/run output

## License

MIT (see `LICENSE`).
