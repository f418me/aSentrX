import logging
import os
import logfire

# These are read when the module is imported, but configure_logging() applies them.
LOG_FILE_NAME_ENV = os.getenv("LOG_FILE_NAME", "asentrx_default.log")
LOG_LEVEL_FILE_STR_ENV = os.getenv("LOG_LEVEL_FILE", "INFO")
LOG_LEVEL_CONSOLE_STR_ENV = os.getenv("LOG_LEVEL_CONSOLE", "DEBUG")
CONSOLE_LOGGING_ENABLED_ENV = os.getenv("CONSOLE_LOGGING_ENABLED", "True").lower() in ("true", "1", "t", "yes")

# --- Application Logger Name ---
# This constant defines the base name for loggers within this application.
# Modules can then get child loggers, e.g., logging.getLogger(f"{APP_LOGGER_NAME}.parser")
APP_LOGGER_NAME = "aSentrX"

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
    Configures the application's logging system.
    This function should be called once at the application's startup.
    It sets up handlers and formatters on the application's base logger
    (defined by APP_LOGGER_NAME).

    Loggers obtained via logging.getLogger() in other modules will inherit this
    configuration if their names are part of the APP_LOGGER_NAME hierarchy
    (e.g., logging.getLogger(f"{APP_LOGGER_NAME}.submodule")).

    This is analogous to calling logging.basicConfig() but provides more control
    and reads configuration from environment variables (via .env).
    """
    global _logging_configured
    if _logging_configured:
        # If called again, we can log a debug message or just return.
        # Re-configuring might be okay if handlers are cleared, but generally, it's once.
        # logging.getLogger(APP_LOGGER_NAME).debug("Logging system already configured. Skipping.")
        return

    # Get the application's base logger.
    # Configuring this logger (and its handlers) will affect all child loggers
    # unless they have specific overriding configurations (which is less common for basic setup).
    app_base_logger = logging.getLogger(APP_LOGGER_NAME)

    # Set the level for the logger itself.
    # This determines the lowest severity of messages that the logger will process.
    # Handlers attached to this logger will then filter messages based on their own levels.
    # Setting it to DEBUG here means the logger will pass all messages from DEBUG upwards
    # to its handlers.
    app_base_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers from this logger to ensure a clean setup,
    # especially if this function could be called in a context where the logger
    # might have been manipulated elsewhere (e.g., by third-party libraries, though rare for named loggers).
    if app_base_logger.hasHandlers():
        app_base_logger.handlers.clear()

    # Define a common formatter for all handlers.
    # See LogRecord attributes in Python docs for available fields.
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S' # Example date format
    )

    # --- File Handler Setup ---
    try:
        file_log_level = get_numeric_loglevel(LOG_LEVEL_FILE_STR_ENV)
    except ValueError as e:
        # If logger config is invalid, print to stderr and raise to stop app.
        print(f"CRITICAL ERROR: Invalid LOG_LEVEL_FILE ('{LOG_LEVEL_FILE_STR_ENV}'): {e}. "
              f"Please check your .env file or environment variables.")
        raise # Re-raise to halt execution if logging can't be set up.

    fh = logging.FileHandler(LOG_FILE_NAME_ENV, encoding='utf-8')
    fh.setLevel(file_log_level) # Set the level for this specific handler.
    fh.setFormatter(formatter)
    app_base_logger.addHandler(fh)

    # --- Console Handler Setup (Optional) ---
    console_log_level_num = None # To store the numeric level for the confirmation message
    if CONSOLE_LOGGING_ENABLED_ENV:
        try:
            console_log_level_num = get_numeric_loglevel(LOG_LEVEL_CONSOLE_STR_ENV)
        except ValueError as e:
            print(f"CRITICAL ERROR: Invalid LOG_LEVEL_CONSOLE ('{LOG_LEVEL_CONSOLE_STR_ENV}'): {e}. "
                  f"Please check your .env file or environment variables.")
            raise

        ch = logging.StreamHandler() # Defaults to sys.stderr
        ch.setLevel(console_log_level_num) # Set the level for this specific handler.
        ch.setFormatter(formatter)
        app_base_logger.addHandler(ch)

    # --- Logfire  Setup ---
    logfire.configure(token=os.getenv("LOGFIRE_TOKEN"),environment=os.getenv("LOGFIRE_ENVIRONMENT", "local"))
    logfire.instrument_pydantic_ai()

    _logging_configured = True

    # --- Confirmation Log ---
    # Use a child logger to log confirmation. This also tests that the hierarchy works.
    config_logger = logging.getLogger(f"{APP_LOGGER_NAME}.config")

    console_status_msg = "Disabled"
    if CONSOLE_LOGGING_ENABLED_ENV and console_log_level_num is not None:
        console_status_msg = f"Enabled (Level: {logging.getLevelName(console_log_level_num)})"

    config_logger.info(
        f"Logging for '{APP_LOGGER_NAME}' initialized. "
        f"Base logger level: {logging.getLevelName(app_base_logger.getEffectiveLevel())}. "
        f"File Handler: '{LOG_FILE_NAME_ENV}' (Level: {logging.getLevelName(file_log_level)}). "
        f"Console Handler: {console_status_msg}."
    )