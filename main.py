import os
import time
import signal
import threading
import logging
from dotenv import load_dotenv
from ai.asentrx_agent import ContentAnalyzer

from truthbrush import Api

from utils import StatusParser
from utils.logger_config import configure_logging, APP_LOGGER_NAME # Import configuration and base logger name

load_dotenv()


try:
    configure_logging()
except ValueError:
    print("CRITICAL: Failed to configure logging. Exiting.")
    exit(1)

logger = logging.getLogger(f"{APP_LOGGER_NAME}.main_app") # Step 3: Get main logger


TARGET_USERNAME = os.getenv("TARGET_USERNAME", "realDonaldTrump")

try:
    FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "60"))
    if FETCH_INTERVAL_SECONDS <= 0:
        logger.warning(f"FETCH_INTERVAL_SECONDS ('{os.getenv('FETCH_INTERVAL_SECONDS')}') was invalid, defaulting to 60s.")
        FETCH_INTERVAL_SECONDS = 60
except ValueError:
    logger.warning(f"FETCH_INTERVAL_SECONDS ('{os.getenv('FETCH_INTERVAL_SECONDS')}') was not a valid integer, defaulting to 60s.")
    FETCH_INTERVAL_SECONDS = 60


INITIAL_SINCE_ID_STR = os.getenv("INITIAL_SINCE_ID")

# Convert an empty string from .env to None, as truthbrush expects None for no since_id filter
INITIAL_SINCE_ID = INITIAL_SINCE_ID_STR if INITIAL_SINCE_ID_STR and INITIAL_SINCE_ID_STR.strip() else None

API_VERBOSE_OUTPUT_STR = os.getenv("API_VERBOSE_OUTPUT", "False").lower()

# Convert common string representations of boolean ("true", "1", etc.) to an actual boolean
API_VERBOSE_OUTPUT = API_VERBOSE_OUTPUT_STR in ("true", "1", "t", "yes")

shutdown_event = threading.Event()


class ASentrX:
    """
    Main class for the aSentrX application.
    Handles fetching, parsing, and logging social media statuses periodically.
    """
    def __init__(self, username: str, initial_since_id: str | None = None):
        self.api = Api()
        self.username = username
        self.last_known_id = initial_since_id
        logger.info(f"ASentrX_Main instance initialized for user: '{self.username}'. "
                    f"Initial since_id: {self.last_known_id or 'None'}.") # Log 'None' explicitly if None
        logger.debug(f"Instance configuration - Fetch interval: {FETCH_INTERVAL_SECONDS}s. "
                     f"Truthbrush API Verbose: {API_VERBOSE_OUTPUT}.")

    def fetch_and_process_statuses(self):
        """
        Fetches new statuses since the last_known_id, processes them using StatusParser,
        logs relevant information, and updates the last_known_id.
        """
        logger.debug(f"Attempting to fetch statuses for '{self.username}' since_id: {self.last_known_id or 'None'}.")

        try:
            statuses_generator = self.api.pull_statuses(  # Rename to indicate it's a generator
                username=self.username,
                replies=False,
                verbose=API_VERBOSE_OUTPUT,
                since_id=self.last_known_id
            )
            # Convert the generator to a list to allow reversal and multiple accesses
            statuses = list(statuses_generator)

        except Exception as e:
            logger.error(f"Error during API call to fetch statuses for '{self.username}': {e}", exc_info=True)
            return

        if not statuses:
            logger.info(f"No new statuses found for '{self.username}' since id {self.last_known_id or 'None'}.")
            return

        # The TruthSocial API typically returns statuses newest first.
        # Iterate in reverse if you want to log the oldest of the new statuses first (more chronological).
        # However, for updating `last_known_id`, the actual newest (statuses[0]) is key.
        for status_dict in reversed(statuses):
            # StatusParser expects a string representation of the dictionary
            status_string = str(status_dict)
            parser = StatusParser(status_string) # Ensure status_parser.py is available

            if parser.is_valid():
                status_id = parser.id
                created_at = parser.created_at
                content_cleaned = parser.get_content(clean_html=True)
                account_username = parser.account_username # Using the property from StatusParser

                # Prepare a content snippet for logging, replacing newlines for better log readability.
                content_preview = "N/A"
                if content_cleaned:
                    content_preview = content_cleaned.replace('\n', ' ').replace('\r', '')[:150]

                logger.info(
                    f"New Status Parsed: ID={status_id}, CreatedAt='{created_at}', "
                    f"User='{account_username or 'N/A'}', " # Handle if username is None
                    f"ContentSnippet (cleaned): \"{content_preview}...\""
                )
                # --- Invoke AI Agent if content exists ---
                # HIER wird geprüft, ob `content_cleaned` existiert:
                if content_cleaned and content_cleaned.strip():
                    content_analyzer =ContentAnalyzer()
                    content_analyzer.analyze_content(content_cleaned)
                    logger.debug(
                        f"AI agent invocation for status ID {status_id}.")
                else:
                    logger.debug(f"Status ID {status_id} has no text content. Skipping AI agent.")
                # For debugging or more detailed analysis, you might log the full cleaned content:
                # logger.debug(f"Full Cleaned Content for Status ID {status_id}: {content_cleaned}")
            else:
                logger.warning(f"Failed to parse a status. Parser Error: {parser.parse_error}. "
                               f"Problematic raw data snippet (first 100 chars): {status_string[:100]}...")

        # After processing all statuses in the batch, update last_known_id
        # to the ID of the newest status (which is statuses[0] if the list is not empty).
        if statuses: # Should generally be true if we reached here after the 'if not statuses:' check
            potential_newest_id = statuses[0].get('id') # Get ID from the first status (the newest)
            if potential_newest_id:
                # Robust ID comparison: Assumes IDs are numeric strings where higher numbers are newer.
                # This may need adjustment if IDs have a different structure or comparison method.
                try:
                    # True if no previous ID, or if the new ID is numerically greater than the last known one.
                    is_newer = self.last_known_id is None or \
                               (isinstance(self.last_known_id, str) and int(potential_newest_id) > int(self.last_known_id))
                except (ValueError, TypeError): # Fallback if IDs are not (or not always) convertible to int
                    is_newer = self.last_known_id is None or potential_newest_id > self.last_known_id
                    logger.debug(f"Could not compare status IDs ({self.last_known_id}, {potential_newest_id}) numerically, used string comparison.")


                if is_newer:
                    logger.info(f"Updating last_known_id from '{self.last_known_id or 'None'}' to '{potential_newest_id}'.")
                    self.last_known_id = potential_newest_id
                else:
                    # This case can occur if the API returns statuses that are not strictly newer
                    # than last_known_id, or if IDs are not perfectly sequential/comparable as numbers.
                    logger.debug(f"Newest ID in batch ('{potential_newest_id}') is not considered newer than "
                                 f"current last_known_id ('{self.last_known_id or 'None'}'). Not updating.")
            else:
                logger.warning("The newest status in the fetched batch does not have an 'id' field, cannot update last_known_id.")

    def run(self, interval_seconds: int):
        """
        Main operational loop for the application.
        Periodically calls fetch_and_process_statuses().
        The loop continues until the global shutdown_event is set.
        """
        logger.info(f"ASentrX_Main run loop starting. Statuses will be fetched every {interval_seconds} seconds.")
        try:
            while not shutdown_event.is_set():
                self.fetch_and_process_statuses()
                # Wait for the specified interval.
                # The wait is interruptible by shutdown_event.set() for graceful exit.
                logger.debug(f"Waiting for {interval_seconds} seconds before next fetch cycle...")
                shutdown_event.wait(interval_seconds)
        except Exception as e: # Catch any unexpected critical error in the main run loop
            logger.critical(f"A critical error occurred in the ASentrX_Main run loop: {e}", exc_info=True)
        finally:
            logger.info("ASentrX_Main run loop has finished.")

def signal_handler(signum, frame):
    """
    Handles termination signals like SIGINT (Ctrl+C) and SIGTERM.
    Sets the shutdown_event to allow the main loop to exit gracefully.
    """
    # Log the received signal by its name for clarity
    try:
        signal_name = signal.Signals(signum).name
    except AttributeError: # For older Python versions or environments where Signals might not have .name
        signal_name = f"Signal {signum}"

    logger.warning(f"{signal_name} received. Initiating graceful shutdown...")
    shutdown_event.set() # Signal the main loop and other waiting threads to terminate

if __name__ == "__main__":
    # Register signal handlers to catch termination signals for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Handles Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Handles `kill` command (default signal)

    # Logger is already configured by configure_logging() called at the top.
    # We can use the 'logger' instance defined after configure_logging().
    logger.info(f"aSentrX application ({APP_LOGGER_NAME}) is starting up...")
    logger.info(f"Configuration - Target User: '{TARGET_USERNAME}', "
                f"Fetch Interval: {FETCH_INTERVAL_SECONDS}s, "
                f"Initial Since ID: {INITIAL_SINCE_ID or 'None'}.")

    # Initialize the main application logic class
    app = ASentrX(username=TARGET_USERNAME, initial_since_id=INITIAL_SINCE_ID)

    # Start the main processing loop. This will block until shutdown_event is set.
    app.run(interval_seconds=FETCH_INTERVAL_SECONDS)

    logger.info(f"aSentrX application ({APP_LOGGER_NAME}) has shut down.")