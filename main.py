import os
import signal
import threading
import logging
from dotenv import load_dotenv
from utils.logger_config import configure_logging, APP_LOGGER_NAME 
from socialmedia.truesocial import TrueSocial

load_dotenv()


try:
    configure_logging()
except ValueError:
    print("CRITICAL: Failed to configure logging. Exiting.")
    exit(1)

logger = logging.getLogger(f"{APP_LOGGER_NAME}.main_app") # Haupt-Logger für main.py




TARGET_USERNAME = os.getenv("TARGET_USERNAME", "realDonaldTrump")
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "60"))
INITIAL_SINCE_ID_STR = os.getenv("INITIAL_SINCE_ID")
INITIAL_SINCE_ID = INITIAL_SINCE_ID_STR if INITIAL_SINCE_ID_STR and INITIAL_SINCE_ID_STR.strip() else None

API_VERBOSE_OUTPUT_STR = os.getenv("API_VERBOSE_OUTPUT", "False").lower()
API_VERBOSE_OUTPUT = API_VERBOSE_OUTPUT_STR in ("true", "1", "t", "yes")

shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """
    Handles termination signals like SIGINT (Ctrl+C) and SIGTERM.
    Sets the shutdown_event to allow the main loop to exit gracefully.
    """
    try:
        signal_name = signal.Signals(signum).name
    except AttributeError:
        signal_name = f"Signal {signum}"

    logger.warning(f"{signal_name} received. Initiating graceful shutdown...")
    shutdown_event.set()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"aSentrX application ({APP_LOGGER_NAME}) is starting up...")

    app = TrueSocial(
        username=TARGET_USERNAME,
        fetch_interval_seconds=FETCH_INTERVAL_SECONDS,
        api_verbose_output=API_VERBOSE_OUTPUT,
        initial_since_id=INITIAL_SINCE_ID
    )

    app.run(
        shutdown_event=shutdown_event
    )

    logger.info(f"aSentrX application ({APP_LOGGER_NAME}) has shut down.")
