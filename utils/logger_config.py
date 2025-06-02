import os
import logfire
import logging
import sentry_sdk

LOG_LEVEL_CONSOLE_STR_ENV = os.getenv("LOG_LEVEL_CONSOLE", "INFO") # Default to INFO for console

PROD_EXECUTION_ENV = os.getenv("PROD_EXECUTION", "False").lower() == "true" #

# --- Application Logger Name ---
# This constant defines the base name for loggers within this application.
# Modules can then get child loggers, e.g., logging.getLogger(f"{APP_LOGGER_NAME}.parser")
APP_LOGGER_NAME = "aSentrX"


if PROD_EXECUTION_ENV:
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            # Add data like request headers and IP for users,
            # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
            send_default_pii=True,
        )


def get_numeric_loglevel(loglevel_str: str) -> int:
    """
    Converts a log level string (case-insensitive) to its Python logging numeric value.
    This function is consistent with the example in the Python Logging HOWTO
    for parsing log levels from strings (e.g., command-line arguments or config files).

    Args:
        loglevel_str: The log level string (e.g., "DEBUG", "info").

    Returns:
        The numeric logging level constant (e.g., logging.DEBUG).

    Raises:
        ValueError: If the loglevel_str is not a valid Python logging level name.
    """
    # Convert to upper case to allow case-insensitive level specification.
    numeric_level = getattr(logging, loglevel_str.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level string: '{loglevel_str}'")
    return numeric_level

_logging_configured = False # Module-level flag to ensure configuration happens only once

def configure_logging():
    """
    Configures the application's logging system for console output.
    This function should be called once at the application's startup.
    It sets up a console handler on the application's base logger
    (defined by APP_LOGGER_NAME).

    Loggers obtained via logging.getLogger() in other modules will inherit this
    configuration if their names are part of the APP_LOGGER_NAME hierarchy.
    """
    global _logging_configured
    if _logging_configured:
        # logging.getLogger(APP_LOGGER_NAME).debug("Logging system already configured. Skipping.")
        return

    app_base_logger = logging.getLogger(APP_LOGGER_NAME)

    # Set the level for the logger itself to DEBUG.
    # This allows handlers to filter messages based on their own more specific levels.
    # If this was INFO, a console handler set to DEBUG would never receive DEBUG messages.
    app_base_logger.setLevel(logging.DEBUG)

    if app_base_logger.hasHandlers():
        app_base_logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- Console Handler Setup (Always Enabled) ---
    try:
        console_log_level_num = get_numeric_loglevel(LOG_LEVEL_CONSOLE_STR_ENV)
    except ValueError as e:
        # Critical error if console log level is invalid. Print and raise.
        print(f"CRITICAL ERROR: Invalid LOG_LEVEL_CONSOLE ('{LOG_LEVEL_CONSOLE_STR_ENV}'): {e}. "
              f"Please check your .env file or environment variables.")
        raise # Re-raise to halt execution

    ch = logging.StreamHandler() # Defaults to sys.stderr, which is fine. For stdout: logging.StreamHandler(sys.stdout)
    ch.setLevel(console_log_level_num)
    ch.setFormatter(formatter)
    app_base_logger.addHandler(ch)

    # --- Logfire Setup ---
    # Ensure LOGFIRE_TOKEN and LOGFIRE_ENVIRONMENT are set in your environment.
    # LOGFIRE_ENVIRONMENT might be 'fly', 'local', 'staging', 'production' etc.
    logfire_token = os.getenv("LOGFIRE_TOKEN")
    logfire_env = os.getenv("LOGFIRE_ENVIRONMENT", "local") # Default to 'local' if not set

    if logfire_token:
        logfire.configure(token=logfire_token, environment=logfire_env)
        logfire.instrument_pydantic_ai()

    else:
        # Log a warning if Logfire token is not found, so it's clear it's not active.
        app_base_logger.warning("LOGFIRE_TOKEN not found. Logfire will not be configured.")


    _logging_configured = True

    config_logger = logging.getLogger(f"{APP_LOGGER_NAME}.config")
    config_logger.info(
        f"Logging for '{APP_LOGGER_NAME}' initialized. "
        f"Base logger level: {logging.getLevelName(app_base_logger.getEffectiveLevel())}. "
        f"Console Handler: Level {logging.getLevelName(console_log_level_num)}."
        f" Logfire configured: {'Yes' if logfire_token else 'No (LOGFIRE_TOKEN not set)'} (Env: {logfire_env})."
    )
