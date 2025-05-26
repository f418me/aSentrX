import logging
import os
import threading

import logfire
from truthbrush import Api
from utils import StatusParser  # Assuming StatusParser is in utils.status_parser
from ai.asentrx_agent import ContentAnalyzer
from utils.logger_config import APP_LOGGER_NAME

# --- Trading Related Imports and Configuration --- START ---
from exchanges.bitfinex_trader import BitfinexTrader
from trader.trader import Trader

logger = logging.getLogger(f"{APP_LOGGER_NAME}.TrueSocial")

# --- TRADING PARAMETERS (ADJUST THESE AS NEEDED) ---
# These will be used if PROD_EXECUTION is True
PROD_EXECUTION_ENABLED = os.getenv("PROD_EXECUTION", "False").lower() == "true"

TRADE_SYMBOL = "tBTCF0:USTF0"  # Default trading symbol
ORDER_LEVERAGE = 10  # Default leverage

# Amounts (positive for BUY, negative for SELL)
# You can have different amounts for different confidence levels or topics if desired
ORDER_AMOUNT_BUY_HIGH_CONF = 0.001  # e.g., for "up" with confidence >= 0.9
ORDER_AMOUNT_SELL_HIGH_CONF = -0.001  # e.g., for "down" with confidence >= 0.9
ORDER_AMOUNT_BUY_MED_CONF = 0.0005  # e.g., for "up" with confidence >= 0.8 and < 0.9
ORDER_AMOUNT_SELL_MED_CONF = -0.0005  # e.g., for "down" with confidence >= 0.8 and < 0.9

# Limit Offset Percentages (positive values)
# Trader class applies: BUY_LIMIT = PRICE * (1 + OFFSET), SELL_LIMIT = PRICE * (1 - OFFSET)
# So, a positive offset makes buy limits higher and sell limits lower.
LIMIT_OFFSET_BUY = 0.005  # 0.5% above market for buy limit
LIMIT_OFFSET_SELL = 0.005  # 0.5% below market for sell limit (using same for simplicity here)


# --- Trading Related Imports and Configuration --- END ---


class TrueSocial:
    """
    Main class for the TrueSocial application.
    Handles fetching, parsing, analyzing, and potentially trading based on social media statuses.
    """

    def __init__(self, username: str, fetch_interval_seconds: int, api_verbose_output: bool,
                 initial_since_id: str | None = None):
        self.api = Api()
        self.username = username
        self.last_known_id = initial_since_id
        self.interval_seconds = fetch_interval_seconds
        self.api_verbose_output = api_verbose_output
        self.content_analyzer = ContentAnalyzer()  # Initialize analyzer here

        # --- Trader Initialization --- START ---
        self.my_trader: Trader | None = None
        if PROD_EXECUTION_ENABLED:
            logger.info("PROD_EXECUTION is enabled. Attempting to initialize Bitfinex Trader.")
            try:
                # Assumes BFX_API_KEY and BFX_API_SECRET are in .env
                bfx_wrapper = BitfinexTrader(default_symbol=TRADE_SYMBOL)
                if bfx_wrapper.bfx_client:  # Check if client was successfully created (keys were present)
                    self.my_trader = Trader(bfx_trader=bfx_wrapper)
                    logger.info("Bitfinex Trader initialized successfully for PROD_EXECUTION.")
                else:
                    logger.warning(
                        "PROD_EXECUTION is True, but Bitfinex client could not be initialized (API keys missing or invalid?). Trading will be skipped.")
            except Exception as e:
                logger.error(f"Failed to initialize Bitfinex Trader for PROD_EXECUTION: {e}", exc_info=True)
                self.my_trader = None  # Ensure it's None on failure
        else:
            logger.info("PROD_EXECUTION is disabled. Trader will not be initialized.")
        # --- Trader Initialization --- END ---

        logger.info(f"TrueSocial instance initialized for user: '{self.username}'. "
                    f"Initial since_id: {self.last_known_id or 'None'}.")

        logger.debug(f"Instance configuration - Fetch interval: {fetch_interval_seconds}s. "
                     f"Truthbrush API Verbose: {self.api_verbose_output}.")

    def _execute_trade_logic(self, analysis_result, status_id_for_log: str):
        """
        Contains the logic to decide and execute trades based on analysis_result.
        This is called only if PROD_EXECUTION_ENABLED and self.my_trader is available.
        """
        if not self.my_trader:
            logger.warning(
                f"Status ID [{status_id_for_log}]: Trade execution logic called, but trader is not available. Skipping.")
            return

        topic = analysis_result.topic_classification
        direction = analysis_result.price_direction
        confidence = analysis_result.price_confidence  # This is price_confidence

        # Ensure essential data is present for trading decisions
        if not topic or not direction or confidence is None:  # 'confidence' here refers to price_confidence
            # Prepare strings for logging, handling None values gracefully for all optional fields
            topic_str = topic if topic is not None else "N/A"
            direction_str = direction if direction is not None else "N/A"
            confidence_str = f"{confidence:.2f}" if confidence is not None else "N/A"
            topic_confidence_str = f"{analysis_result.topic_confidence:.2f}" if analysis_result.topic_confidence is not None else "N/A"

            logger.info(
                f"Status ID [{status_id_for_log}]: Incomplete analysis data for trading. "
                f"Topic='{topic_str}' (TopicConf: {topic_confidence_str}), "
                f"Direction='{direction_str}' (PriceConf: {confidence_str}). No trading action."
            )
            return

        topic_lower = topic.lower()
        direction_lower = direction.lower()

        # Confidence is already checked for None above, so direct formatting is safe here
        log_prefix = f"Status ID [{status_id_for_log}] Topic [{topic_lower}] Direction [{direction_lower}] Confidence [{confidence:.2f}]:"

        if topic_lower not in ["bitcoin", "market", "tariffs"]:
            logger.info(f"{log_prefix} Topic not relevant for automated trading ('{topic_lower}'). No action.")
            return

        # --- Prepare Order Parameters (to be filled based on conditions) ---
        order_to_execute = None  # Will store dict: {amount, limit_offset_percentage}

        if direction_lower == "up":
            if confidence >= 0.9:
                logger.info(f"{log_prefix} ACTION: High-confidence UP. Preparing BUY order.")
                logfire.info(f"{log_prefix} ACTION: High-confidence UP. Preparing BUY order.")
                order_to_execute = {
                    "amount": ORDER_AMOUNT_BUY_HIGH_CONF,
                    "limit_offset_percentage": LIMIT_OFFSET_BUY,
                    "description": "High-Confidence UP"
                }
            elif confidence >= 0.8:  # This implies confidence < 0.9 due to the if/elif
                logger.info(f"{log_prefix} ACTION: Medium-confidence UP. Preparing BUY order.")
                logfire.info(f"{log_prefix} ACTION: Medium-confidence UP. Preparing BUY order.")
                order_to_execute = {
                    "amount": ORDER_AMOUNT_BUY_MED_CONF,
                    "limit_offset_percentage": LIMIT_OFFSET_BUY,
                    "description": "Medium-Confidence UP"
                }
            else:
                logger.info(f"{log_prefix} Predicted UP, but confidence ({confidence:.2f}) is below 0.8. No action.")

        elif direction_lower == "down":
            if confidence >= 0.9:
                logger.info(f"{log_prefix} ACTION: High-confidence DOWN. Preparing SELL order.")
                logfire.info(f"{log_prefix} ACTION: High-confidence DOWN. Preparing SELL order.")
                order_to_execute = {
                    "amount": ORDER_AMOUNT_SELL_HIGH_CONF,
                    "limit_offset_percentage": LIMIT_OFFSET_SELL,
                    "description": "High-Confidence DOWN"
                }
            elif confidence >= 0.8:  # This implies confidence < 0.9
                logger.info(f"{log_prefix} ACTION: Medium-confidence DOWN. Preparing SELL order.")
                logfire.info(f"{log_prefix} ACTION: Medium-confidence DOWN. Preparing SELL order.")
                order_to_execute = {
                    "amount": ORDER_AMOUNT_SELL_MED_CONF,
                    "limit_offset_percentage": LIMIT_OFFSET_SELL,
                    "description": "Medium-Confidence DOWN"
                }
            else:
                logger.info(f"{log_prefix} Predicted DOWN, but confidence ({confidence:.2f}) is below 0.8. No action.")

        elif direction_lower == "neutral":
            logger.info(f"{log_prefix} Predicted NEUTRAL. No action.")
        else:
            logger.warning(f"{log_prefix} Unknown price direction '{direction_lower}'. No action.")

        # --- Execute Order if Parameters are Set ---
        if order_to_execute:
            logger.info(
                f"{log_prefix} Attempting to execute {order_to_execute['description']} order. "
                f"Amount: {order_to_execute['amount']}, Leverage: {ORDER_LEVERAGE}, "
                f"Limit Offset: {order_to_execute['limit_offset_percentage'] * 100:.2f}%"
            )
            try:
                self.my_trader.execute_order(
                    symbol=TRADE_SYMBOL,
                    amount=order_to_execute["amount"],
                    leverage=ORDER_LEVERAGE,
                    limit_offset_percentage=order_to_execute["limit_offset_percentage"]
                )
            except Exception as e:
                logger.error(
                    f"{log_prefix} EXCEPTION during order execution for {order_to_execute['description']}: {e}",
                    exc_info=True)

    def fetch_and_process_statuses(self):
        """
        Fetches new statuses, processes them, analyzes content, and potentially triggers trades.
        """
        logger.debug(f"Attempting to fetch statuses for '{self.username}' since_id: {self.last_known_id or 'None'}.")

        try:
            statuses_generator = self.api.pull_statuses(
                username=self.username,
                replies=False,
                verbose=self.api_verbose_output,
                since_id=self.last_known_id
            )
            statuses = list(statuses_generator)

        except Exception as e:
            logger.error(f"Error during API call to fetch statuses for '{self.username}': {e}", exc_info=True)
            return

        if not statuses:
            logger.info(f"No new statuses found for '{self.username}' since id {self.last_known_id or 'None'}.")
            return

        for status_dict in reversed(statuses):  # Process oldest first to maintain order
            status_string = str(status_dict)
            parser = StatusParser(status_string)

            if not parser.is_valid():
                logger.warning(f"Failed to parse a status. Parser Error: {parser.parse_error}. "
                               f"Problematic raw data snippet (first 100 chars): {status_string[:100]}...")
                continue  # Skip to next status

            status_id = parser.id
            created_at = parser.created_at
            content_cleaned = parser.get_content(clean_html=True)
            account_username = parser.account_username

            content_preview = "N/A"
            if content_cleaned:
                content_preview = content_cleaned.replace('\n', ' ').replace('\r', '')[:150]

            logger.info(
                f"New Status Parsed: ID={status_id}, CreatedAt='{created_at}', "
                f"User='{account_username or 'N/A'}', "
                f"ContentSnippet (cleaned): \"{content_preview}...\""
            )

            if content_cleaned and content_cleaned.strip():
                logger.debug(f"Status ID [{status_id}]: Analyzing content...")
                analysis_result = self.content_analyzer.analyze_content(content_cleaned,
                                                                        status_id_for_logging=status_id)

                # --- MODIFIED LOGGING --- START ---
                # Prepare formatted strings for confidence values, handling None
                topic_conf_str = f"{analysis_result.topic_confidence:.2f}" if analysis_result.topic_confidence is not None else "N/A"
                price_conf_str = f"{analysis_result.price_confidence:.2f}" if analysis_result.price_confidence is not None else "N/A"

                # Use "N/A" for None values of classification and direction as well for consistency in logging
                topic_classification_str = analysis_result.topic_classification if analysis_result.topic_classification is not None else "N/A"
                price_direction_str = analysis_result.price_direction if analysis_result.price_direction is not None else "N/A"

                logger.info(
                    f"Status ID [{status_id}] AI Analysis Result: "
                    f"Topic='{topic_classification_str}' (Conf: {topic_conf_str}), "
                    f"Direction='{price_direction_str}' (Conf: {price_conf_str})"
                )
                # --- MODIFIED LOGGING --- END ---

                # --- Trade Execution Logic ---
                if PROD_EXECUTION_ENABLED and self.my_trader:
                    self._execute_trade_logic(analysis_result, status_id_for_log=status_id)
                elif PROD_EXECUTION_ENABLED and not self.my_trader:
                    logger.warning(
                        f"Status ID [{status_id}]: PROD_EXECUTION is True, but trader is not initialized. Trading actions will be skipped.")

            else:  # No clean content to analyze
                logger.debug(
                    f"Status ID [{status_id}] has no text content after cleaning. Skipping AI analysis and trading.")

        # Update last_known_id with the ID of the newest status in the batch
        if statuses:
            # statuses[0] is the newest because truthbrush returns newest first
            potential_newest_id = statuses[0].get('id')
            if potential_newest_id:
                try:
                    # Ensure robust comparison if IDs are numeric strings
                    current_last_id_int = int(self.last_known_id) if self.last_known_id else 0
                    potential_newest_id_int = int(potential_newest_id)
                    is_newer = potential_newest_id_int > current_last_id_int
                except (ValueError, TypeError):
                    # Fallback to string comparison if conversion fails or last_known_id is None
                    is_newer = self.last_known_id is None or potential_newest_id > self.last_known_id
                    logger.debug(
                        f"Could not compare status IDs ({self.last_known_id}, {potential_newest_id}) numerically, used string/None comparison.")

                if is_newer:
                    logger.info(
                        f"Updating last_known_id from '{self.last_known_id or 'None'}' to '{potential_newest_id}'.")
                    self.last_known_id = potential_newest_id
                else:
                    logger.debug(f"Newest ID in batch ('{potential_newest_id}') is not considered newer than "
                                 f"current last_known_id ('{self.last_known_id or 'None'}'). Not updating.")
            else:
                logger.warning(
                    "The newest status in the fetched batch does not have an 'id' field, cannot update last_known_id.")

    def run(self, shutdown_event: threading.Event):
        """
        Main operational loop for the application.
        Periodically calls fetch_and_process_statuses().
        """
        logger.info(
            f"TrueSocial run loop starting for '{self.username}'. Statuses will be fetched every {self.interval_seconds} seconds.")

        try:
            while not shutdown_event.is_set():
                self.fetch_and_process_statuses()
                logger.debug(
                    f"Waiting for {self.interval_seconds} seconds before next fetch cycle for '{self.username}'...")
                # Wait for the interval, but break early if shutdown_event is set
                shutdown_event.wait(self.interval_seconds)
        except Exception as e:
            logger.critical(f"A critical error occurred in the TrueSocial run loop for '{self.username}': {e}",
                            exc_info=True)
        finally:
            logger.info(f"TrueSocial run loop for '{self.username}' has finished.")

