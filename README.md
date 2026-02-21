# aSentrX

aSentrX is an advanced Python application designed for fetching, analyzing, and acting upon social media statuses, primarily from platforms like Truth Social using the `truthbrush` library. It integrates AI-driven content analysis to understand sentiment and potential market impacts, and can execute trades via the Bitfinex API. The system is architected for continuous operation, features robust logging with Logfire, SMS notifications via Twilio, and is deployed using Docker on Fly.io with CI/CD via GitHub Actions.

## Main Features

*   **Social Media Status Fetching**: Retrieves statuses from specific user accounts (e.g., Truth Social).
    *   Supports filtering by `since_id` to load only newer statuses.
    *   Option to exclude replies.
*   **Continuous Monitoring & Processing**: The main application (`main.py`) runs as a service, periodically fetching, parsing, and analyzing new statuses.
*   **AI-Powered Content Analysis**:
    *   Utilizes a `ContentAnalyzer` (powered by `pydantic-ai` and large language models) to analyze status content.
    *   Classifies topics (e.g., market-related, bitcoin, tariffs).
    *   Assesses potential impact and predicts price direction for relevant topics.
*   **Automated Trading**:
    *   Integrates with the Bitfinex API via `BitfinexTrader` and `Trader` classes.
    *   Executes trading orders based on AI analysis results and configurable parameters (amount, leverage, offsets).
*   **SMS Notifications**: Sends real-time alerts for significant events (e.g., trade execution) using Twilio.
*   **Advanced Logging with Logfire**:
    *   Comprehensive application logging.
    *   Specialized logging and tracing for LLM calls and `pydantic-ai` agent interactions using [Logfire](https://logfire.pydantic.dev/).
*   **Dependency management**:
    *   Dependency management with [Poetry](https://python-poetry.org/).
*   **Deployment & CI/CD**:
    *   Containerized with Docker for consistent environments.
    *   Deployed to [Fly.io](https://fly.io/).
    *   Automated deployments from the `master` branch via GitHub Actions.
*   **Status Parsing**:
    *   A dedicated `StatusParser` handles raw status data (e.g., from API calls).
    *   Extracts key attributes (ID, creation date, content, user info).
    *   Cleans HTML from status content.
    *   Robustly handles parsing errors.
*   **Configurability**: Use of environment variables (via `.env` file) for application settings, API keys, and feature flags.

## Prerequisites

*   Python 3.12+
*   [Poetry](https://python-poetry.org/docs/#installation) (for managing dependencies and running the project)
*   Docker (for containerized deployment)
*   Access to services and their API keys:
    *   Truth Social (implicitly, via `truthbrush`)
    *   An LLM provider compatible with `pydantic-ai` (e.g., Groq, OpenAI)
    *   Bitfinex (for trading)
    *   Twilio (for SMS notifications)
    *   Logfire (for enhanced logging)

## Installation and Setup

### 1. Poetry Installation (for local development & contribution)

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-name>
    ```

2.  **Install Poetry** if you haven't already (see official [Poetry installation guide](https://python-poetry.org/docs/#installation)).

3.  **Install project dependencies using Poetry:**
    This command reads the `pyproject.toml` file, resolves dependencies, and installs them into a virtual environment managed by Poetry.
    ```bash
    poetry install
    ```

4.  **Create and configure the `.env` file:**
    Copy the `.env.example` (if provided) to `.env` or create a new `.env` file in the project's root directory. Populate it with your specific configurations and API keys.
    If you use the Decodo proxy, also configure `DECODO_PROXY_MAX_RETRIES` (recommended: `3`).

    **Important:** Add `.env` to your `.gitignore` file to prevent committing sensitive credentials.

### 2. Docker Setup (for Deployment & Consistent Environments)

The project includes a `Dockerfile` for building and running the service.

1.  **Clone the repository (if not already done).**
2.  **Create the `.env` file** in the project's root directory as described above.
3.  **(Optional, but recommended) Create/Review `.dockerignore` file:**
    Ensure this file excludes unnecessary files (like `.git`, `venv`, `__pycache__`, local `.env` if mounted differently) from the Docker build context.

## Starting the Application

The main application (`main.py`) is designed to run continuously.

### With Docker (Recommended for production-like environments)

The project uses Docker Hub for image distribution: `felixfreichur/asentrx:latest`

1.  **Pull and start the pre-built image from Docker Hub:**
    ```bash
    sudo docker pull felixfreichur/asentrx:latest
    sudo docker run -d --name asentrx_container --env-file .env-prod felixfreichur/asentrx:latest
    ```
    The `-d` flag runs the service in detached mode.

2.  **Build and start locally (for development with changes):**
    ```bash
    sudo docker build -t asentrx:local .
    sudo docker run -d --name asentrx_local --env-file .env asentrx:local
    ```

3.  **View logs:**
    ```bash
    sudo docker logs -f asentrx_container
    ```
    For detailed analysis, check your Logfire dashboard.

4.  **Stop the service:**
    ```bash
    sudo docker stop asentrx_container
    sudo docker rm asentrx_container
    ```

### Building and Pushing to Docker Hub

1.  **Build and push the image:**
    ```bash
    sudo docker build -t felixfreichur/asentrx:latest .
    sudo docker login
    sudo docker push felixfreichur/asentrx:latest
    ```

### Manually (using Poetry, for local development)

1.  **Ensure you have completed the Poetry installation and `.env` file setup.**
2.  **Activate the Poetry shell (optional but recommended):**
    ```bash
    poetry shell
    ```
    This activates the virtual environment. If you skip this, preface commands with `poetry run`.

3.  **Start the main script:**
    ```bash
    # If inside poetry shell
    python main.py
    # Or, if not in poetry shell
    poetry run python main.py
    ```
    The application will start, and logs will be sent to the console and Logfire.


## Truth Social Authentication

aSentrX supports two authentication methods for Truth Social via the `truthbrush` library:

### Method 1: Username & Password (OAuth Login)

Set in your `.env`:
```env
TRUTHSOCIAL_USERNAME=your_username
TRUTHSOCIAL_PASSWORD=your_password
```

This performs an OAuth token exchange at startup. **Note:** This method may be blocked by Cloudflare (HTTP 403), especially from non-US IP addresses or datacenter IPs.

### Method 2: Bearer Token (Recommended)

If the OAuth login is blocked, you can extract your session token directly from the browser and bypass the login flow entirely.

**How to extract your `TRUTHSOCIAL_TOKEN`:**

1. Open **https://truthsocial.com** in your browser (Chrome/Firefox/Edge) and **log in** to your account.
2. Open **Developer Tools**:
   - **Mac**: `Cmd + Option + I`
   - **Windows/Linux**: `F12` or `Ctrl + Shift + I`
3. Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4. In the left sidebar, expand **Local Storage** → click on **`https://truthsocial.com`**.
5. Find the key **`truth:auth`** in the list.
6. Click on the value — it contains a JSON object. Copy the value of the **`access_token`** field.
7. Add the token to your `.env` file:

```env
TRUTHSOCIAL_TOKEN=your_access_token_here
```

> **Important:**
> - When `TRUTHSOCIAL_TOKEN` is set, it takes priority over username/password — the OAuth login is skipped entirely.
> - The token **can expire**. If you start getting HTTP 401 errors, extract a fresh token from your browser.
> - You can verify your token works by running: `python experiments/diagnose_truth_auth.py --use-token`

## Logging

*   **Standard Logging**: The application uses Python's `logging` module for console output, configured via `utils/logger_config.py`. The level is set by `LOG_LEVEL_CONSOLE` in `.env`.
*   **Logfire**: This is the primary tool for advanced logging, observability, and tracing, especially for LLM interactions within `pydantic-ai`.
    *   Configure `LOGFIRE_TOKEN` and `LOGFIRE_ENVIRONMENT` in your `.env` file.
    *   Logfire automatically instruments Pydantic and `pydantic-ai`.
    *   View detailed logs, traces, and analytics on your Logfire dashboard.

## SMS Notifications

*   The application can send SMS notifications for critical events (e.g., trade executions) via Twilio.
*   Enable this feature by setting `SMS_NOTIFICATIONS_ENABLED="True"` in `.env`.
*   Configure Twilio credentials (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`) and phone numbers (`TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBER`).

## Deployment to Fly.io

*   The application is designed to be deployed as a Docker container on [Fly.io](https://fly.io/).
*   The `fly.toml` configuration file defines how the application is built and run on the platform.
*   **Environment Variables on Fly.io**: Sensitive information (API keys, tokens from your `.env` file) must be set as "secrets" in your Fly.io app settings:
    ```bash
    fly secrets set VAR_NAME="value" -a your-fly-app-name
    ```
    Repeat for all necessary variables from `.env` file.
*   **GitHub Actions for CI/CD**:
    *   A GitHub Actions workflow (e.g., in `.github/workflows/fly-deploy.yml`) is set up to:
        1.  Trigger on pushes to the `master` branch.
        2.  Build the Docker image.
        3.  Push the image to a container registry (Fly.io has its own).
        4.  Deploy the new image to your Fly.io application using the `flyctl` command-line tool.
    *   The GitHub Actions workflow require a `FLY_API_TOKEN` secret to be configured in your GitHub repository settings for authentication with Fly.io.

## Contributing

Contributions are welcome! Please follow these general steps:
1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Ensure your code follows project conventions and passes any linters/tests.
5.  Install dependencies with `poetry install`.
6.  Test your changes thoroughly.
7.  Submit a pull request with a clear description of your changes.
