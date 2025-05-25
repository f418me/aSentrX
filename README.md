# aSentrX

aSentrX is a collection of Python scripts designed for fetching, storing, and parsing social media statuses, primarily from Truth Social using the `truthbrush` library. It also includes a separate module for interacting with the Bitfinex API and an AI agent for content analysis. The system is designed to run continuously in the background, monitoring for new statuses.

## Main Features

*   **Status Fetching**: Retrieves statuses from a specific Truth Social user account.
    *   Supports filtering by `since_id` to load only newer statuses.
    *   Option to exclude replies.
*   **Continuous Monitoring**: The main script (`main.py`) runs as a service, periodically fetching new statuses.
*   **Data Storage (for utility scripts)**: Saves fetched statuses as raw Python dictionary strings in a text file. Each line corresponds to one status. (Primarily used by `write_raw_status_to_file.py`).
*   **Status Parsing**:
    *   A dedicated parser (`StatusParser`) reads raw status strings (e.g., from a file or directly from an API call).
    *   Extracts specific attributes like ID, creation date, content, and account information (e.g., username).
    *   Cleans HTML tags from the status content.
    *   Tolerantly handles parsing errors.
*   **AI Content Analysis**:
    *   A `ContentAnalyzer` (`asentrx_agent.py`) analyzes the cleaned content of statuses.
    *   Classifies tweets (e.g., market-related, private, other).
    *   Assesses potential impact on Bitcoin price.
    *   Predicts the likely direction of Bitcoin price changes.
*   **Bitfinex API Integration**: A separate script (`bitfinex_rest.py`) demonstrates querying wallet information and other endpoints via the `bfxapi`.
*   **Configurable Logging**: Detailed logging with configurable levels for file and console output.
*   **Docker Support**: Easy deployment and execution with Docker and Docker Compose.

## Prerequisites

*   Python 3.12+ (for manual installation)
*   pip (Python Package Installer, for manual installation)
*   Docker and Docker Compose (for Docker-based deployment)

## Installation and Setup

There are two main ways to install and run aSentrX: Manually or with Docker.

### 1. Manual Installation (for development or specific use cases)

1.  **Clone the repository or create the folder structure manually.**

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: The `truthbrush` entry installs directly from GitHub.*

4.  **Create configuration file `.env`:**
    Create a file named `.env` in the project's root directory. 

5. **Important:** Add `.env` to your `.gitignore` file to avoid accidentally publishing your keys.

### 2. Docker Installation & Setup (Recommended for Deployment)

This method uses Docker to run the application in an isolated container.

1.  **Clone the repository (if not already done).**

2.  **Create configuration file `.env`:**
    Create the `.env` file in the project's root directory as described in the "Manual Installation" section, point 4. Docker Compose will use this file to load environment variables into the container.

3.  **(Optional, but recommended) Create `.dockerignore` file:**
    Create a file named `.dockerignore` in the project's root directory to exclude unnecessary files from the Docker build context:
    ```
    .git
    .venv
    venv/
    __pycache__/
    *.pyc
    *.pyo
    *.pyd
    .env
    logs/
    *.log
    raw_statuses_*.txt
    ```
    *Note: `.env` is listed here because it's mounted directly into the container rather than copied into the image.*

4.  **Build Docker Image (optional, as `docker-compose up --build` also does this):**
    ```bash
    docker build -t asentrx .
    ```

## Starting the Application

### Starting the Main Service (`main.py`)

The main service (`main.py`) is designed to run continuously, fetching and analyzing statuses.

#### With Docker Compose (Recommended)

This is the easiest way to manage the service and its dependencies (like volumes for logs).

1.  **Ensure your `docker-compose.yml` file is configured.**
    An example `docker-compose.yml` might look like this:
    ```yaml
    version: '3.8'

    services:
      asentrx_app:
        build: .
        container_name: asentrx_service
        restart: unless-stopped
        env_file:
          - .env # Loads environment variables from the .env file
        volumes:
          - ./logs:/app/logs # Mounts the local logs folder into the container
          # Optional: If write_raw_status_to_file.py is used within Docker
          # and its output should persist on the host:
          - ./data:/app/data
        # Ensures Python doesn't buffer output, for more direct logs
        environment:
          - PYTHONUNBUFFERED=1
    ```
    *Adjust `LOG_FILE_NAME` in your `.env` file, e.g., `LOG_FILE_NAME="logs/asentrx_app.log"`, so logs end up in the mounted volume.*
    *If you plan to run `write_raw_status_to_file.py` via Docker and want the output file (e.g., `raw_statuses_dump_trump_2025.txt`) to be saved on the host system, set `OUTPUT_FILENAME_RAW_STATUSES` in your `.env` to something like `data/raw_statuses_dump_trump_2025.txt` and ensure the `data` volume is mounted.*

2.  **Start the service:**
    ```bash
    sudo docker compose up --build -d
    ```
    The `-d` parameter starts the service in detached mode (in the background). Without `-d`, you'll see the logs directly.

3.  **View logs:**
    ```bash
    sudo docker compose logs -f asentrx_app
    ```

4.  **Stop the service:**
    ```bash
    sudo docker compose down
    ```

#### Manually (without Docker)

1.  **Ensure you have completed the manual installation and created the `.env` file.**
2.  **Start the main script:**
    ```bash
    python main.py
    ```
    The application will start and begin fetching statuses according to the configuration in `.env`. Logs will be written to the console and/or the log file.

### Running Utility Scripts

These scripts serve specific, mostly one-off tasks.

#### 1. `write_raw_status_to_file.py`: Fetch Statuses and Save to File

This script fetches statuses from Truth Social and saves them.

*   **Configuration:**
    *   Adjust the constants `TARGET_USERNAME`, `SINCE_ID_FILTER`, `OUTPUT_FILENAME_RAW_STATUSES`, `API_VERBOSE_OUTPUT` directly in the `write_raw_status_to_file.py` script if you run it manually (without Docker or without using `main.py`'s environment variables).
    *   If you want to run this script within the Docker context (e.g., using `docker-compose run`) and utilize environment variables from `.env`, you would need to adapt the script to read these variables (similar to `main.py`). By default, it reads its own constants.

*   **Execution (manual):**
    ```bash
    python write_raw_status_to_file.py
    ```
    This will create (or overwrite) the file specified in `OUTPUT_FILENAME_RAW_STATUSES` within the script.

*   **Execution (with Docker Compose, if the script has been adapted to use `.env` or you want to use its default values):**
    Ensure `OUTPUT_FILENAME_RAW_STATUSES` writes to a mounted volume if you want the file to persist on the host (see `docker-compose.yml` example with `/app/data`).
    ```bash
    docker-compose run --rm asentrx_app python write_raw_status_to_file.py
    ```

#### 2. `read_content_from_file.py`: Read and Process Saved Statuses

This script reads the previously saved file, parses each status, and prints information.

*   **Configuration:** Adjust `INPUT_FILENAME` directly in the `read_content_from_file.py` script.
*   **Execution (manual):**
    ```bash
    python read_content_from_file.py
    ```
*   **Execution (with Docker Compose):**
    Ensure `INPUT_FILENAME` reads from a mounted volume.
    ```bash
    docker-compose run --rm asentrx_app python read_content_from_file.py
    ```

#### 3. `analyze_content_with_agent.py`: Test Direct Content Analysis

Tests the `ContentAnalyzer` with sample text.

*   **Configuration:** Requires `.env` variables for the AI model provider (e.g., `MODEL`, `GROQ_API_KEY`).
*   **Execution (manual):**
    ```bash
    python analyze_content_with_agent.py
    ```
*   **Execution (with Docker Compose):**
    ```bash
    docker-compose run --rm asentrx_app python ai/analyze_content_with_agent.py
    ```

#### 4. `bitfinex_rest.py`: Bitfinex API Interaction

Demonstrates interaction with the Bitfinex API.

*   **Configuration:** Requires `BFX_API_KEY` and `BFX_API_SECRET` in the `.env` file.
*   **Execution (manual):**
    ```bash
    python bitfinex_rest.py
    ```
*   **Execution (with Docker Compose):**
    ```bash
    docker-compose run --rm asentrx_app python bitfinex_rest.py
    ```

#### 5. `pull_status.py`: Simple Status Fetch Test

A simple example script that fetches statuses directly from Truth Social and prints them to the console.

*   **Configuration:** Parameters are set directly in the script.
*   **Execution (manual):**
    ```bash
    python pull_status.py
    ```
*   **Execution (with Docker Compose):**
    ```bash
    docker-compose run --rm asentrx_app python pull_status.py
    ```

## Logging

The application uses Python's `logging` module. Configuration is done via environment variables read by `utils/logger_config.py` (see `.env` example).
When using Docker, ensure the log folder/file is mounted to a volume to persist logs on the host system.
