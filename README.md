# aSentrX
https://github.com/stanfordio/truthbrush/blob/main/README.md
aSentrX is a collection of Python scripts designed for fetching, storing, and parsing social media statuses, primarily from Truth Social using the `truthbrush` library. It also includes a separate module for interacting with the Bitfinex API.

## Main Features

*   **Status Fetching**: Retrieves statuses from a specific Truth Social user account.
    *   Supports filtering by `since_id` to load only newer statuses.
    *   Option to exclude replies.
*   **Data Storage**: Saves the fetched statuses as raw Python dictionary strings in a text file. Each line corresponds to one status.
*   **Status Parsing**:
    *   A dedicated parser (`StatusParser`) reads the raw status strings from the file.
    *   Extracts specific attributes like ID, creation date, content, and account information (e.g., username).
    *   Cleans HTML tags from the status content.
    *   Tolerantly handles parsing errors.
*   **Bitfinex API Integration**: A separate script demonstrates querying wallet information via the `bfxapi`.


## Prerequisites

*   Python 3.12+
*   pip (Python Package Installer)

## Installation

1.  **Clone the repository (if it is one) or create the folder structure manually.**

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
   
    ```
    Install the packages:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: The `truthbrush` entry installs directly from GitHub, as you specified.*

4.  **For `bitfinex.py` (optional):**
    Create a file named `.env` in the project's root directory and add your Bitfinex API keys:
    ```env
    BFX_API_KEY="YOUR_API_KEY"
    BFX_API_SECRET="YOUR_API_SECRET"
    ```
    **Important:** Add `.env` to your `.gitignore` file to avoid accidentally publishing your keys.

## Usage

The project has a main workflow consisting of two steps: fetching and saving data, then reading and processing data.

### 1. Fetch Statuses and Save to File (`write_raw_status_to_file.py`)

This script fetches statuses from Truth Social and saves them.

*   **Configuration:** Edit the constants at the beginning of `write_raw_status_to_file.py`:
    *   `TARGET_USERNAME`: The Truth Social username whose statuses are to be fetched (e.g., `"realDonaldTrump"`).
    *   `SINCE_ID_FILTER`: Optional. A status ID. Only statuses newer than this ID will be fetched. Set to `None` or an empty string to fetch all (or leave the default value if appropriate).
    *   `OUTPUT_FILENAME_RAW_STATUSES`: Name of the output file for the raw status data.
    *   `API_VERBOSE_OUTPUT`: `True` or `False` to control the verbose output of the `truthbrush` library during fetching.

*   **Execution:**
    ```bash
    python write_raw_status_to_file.py
    ```
    This will create (or overwrite) the file specified in `OUTPUT_FILENAME_RAW_STATUSES` with the fetched statuses, one status dictionary (as a string) per line.

### 2. Read and Process Saved Statuses (`read_content_from_file.py`)

This script reads the previously saved file, parses each status, and prints information.


*   **Execution:**
    ```bash
    python read_content_from_file.py
    ```
    The script will output the ID, cleaned content, and account username for each valid status in the file. Parsing errors will also be reported.

### Other Scripts

*   **`pull_status.py`**: A simple example script that fetches statuses directly from Truth Social and prints them to the console. Can be used for quick tests or to understand the `truthbrush` API.
*   **`bitfinex.py`**: A separate script that demonstrates how to interact with the Bitfinex API to retrieve wallet information. Requires the `.env` file with API keys.
    ```bash
    python bitfinex.py
    ```




pip install git+https://github.com/stanfordio/truthbrush.git

