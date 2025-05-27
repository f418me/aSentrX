import logging
import os
import threading

import logfire
from truthbrush import Api
from utils import StatusParser
from ai.asentrx_agent import ContentAnalyzer
from utils.logger_config import APP_LOGGER_NAME

from exchanges.bitfinex_trader import BitfinexTrader
from trader.trader import Trader
from utils.sms_notifier import SmsNotifier


logger = logging.getLogger(f"{APP_LOGGER_NAME}.TrueSocial")

PROD_EXECUTION_ENABLED = os.getenv("PROD_EXECUTION", "False").lower() == "true"
SMS_NOTIFICATIONS_ENABLED = os.getenv("SMS_NOTIFICATIONS_ENABLED", "False").lower() == "true"

TRADE_SYMBOL = "tBTCF0:USTF0"
ORDER_LEVERAGE = 10

ORDER_AMOUNT_BUY_HIGH_CONF = 0.001
ORDER_AMOUNT_SELL_HIGH_CONF = -0.001
ORDER_AMOUNT_BUY_MED_CONF = 0.0005
ORDER_AMOUNT_SELL_MED_CONF = -0.0005

LIMIT_OFFSET_BUY = 0.005
LIMIT_OFFSET_SELL = 0.005

class TrueSocial:
    def __init__(self, username: str, fetch_interval_seconds: int, api_verbose_output: bool,
                 initial_since_id: str | None = None):
        self.api = Api()
        self.username = username
        self.last_known_id = initial_since_id
        self.interval_seconds = fetch_interval_seconds
        self.api_verbose_output = api_verbose_output
        self.content_analyzer = ContentAnalyzer()

        self.my_trader: Trader | None = None
        if PROD_EXECUTION_ENABLED:
            logger.info("PROD_EXECUTION is enabled. Attempting to initialize Bitfinex Trader.")
            try:
                bfx_wrapper = BitfinexTrader(default_symbol=TRADE_SYMBOL)
                if bfx_wrapper.bfx_client:
                    self.my_trader = Trader(bfx_trader=bfx_wrapper)
                    logger.info("Bitfinex Trader initialized successfully for PROD_EXECUTION.")
                else:
                    logger.warning(
                        "PROD_EXECUTION is True, but Bitfinex client could not be initialized. Trading will be skipped.")
            except Exception as e:
                logger.error(f"Failed to initialize Bitfinex Trader for PROD_EXECUTION: {e}", exc_info=True)
        else:
            logger.info("PROD_EXECUTION is disabled. Trader will not be initialized.")

        self.sms_notifier: SmsNotifier | None = None
        if SMS_NOTIFICATIONS_ENABLED:
            logger.info("SMS_NOTIFICATIONS_ENABLED is True. Initializing SmsNotifier.")
            self.sms_notifier = SmsNotifier()
            if not self.sms_notifier.client:  # Check if Twilio client within notifier failed
                logger.warning(
                    "SmsNotifier initialized, but Twilio client setup failed (check logs from SmsNotifier). SMS will not be sent.")
                self.sms_notifier = None  # Set to None if sub-initialization failed
        else:
            logger.info("SMS_NOTIFICATIONS_ENABLED is False. SmsNotifier will not be used.")

        logger.info(f"TrueSocial instance initialized for user: '{self.username}'. "
                    f"Initial since_id: {self.last_known_id or 'None'}.")
        logger.debug(f"Instance configuration - Fetch interval: {fetch_interval_seconds}s. "
                     f"Truthbrush API Verbose: {self.api_verbose_output}.")

    def _execute_trade_logic(self, analysis_result, status_id_for_log: str):
        if not self.my_trader:
            logger.warning(
                f"Status ID [{status_id_for_log}]: Trade execution logic called, but trader is not available. Skipping.")
            return

        topic = analysis_result.topic_classification
        direction = analysis_result.price_direction
        confidence = analysis_result.price_confidence

        if not topic or not direction or confidence is None:
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
        log_prefix = f"Status ID [{status_id_for_log}] Topic [{topic_lower}] Direction [{direction_lower}] Confidence [{confidence:.2f}]:"

        if topic_lower not in ["bitcoin", "market", "tariffs"]:
            logger.info(f"{log_prefix} Topic not relevant for automated trading ('{topic_lower}'). No action.")
            return

        order_to_execute = None
        sms_message_body = None  # To store the body for SMS notification

        if direction_lower == "up":
            if confidence >= 0.9:
                desc = "High-Confidence UP"
                logger.info(f"{log_prefix} ACTION: {desc}. Preparing BUY order.")
                logfire.info(f"{log_prefix} ACTION: {desc}. Preparing BUY order.")
                order_to_execute = {"amount": ORDER_AMOUNT_BUY_HIGH_CONF, "limit_offset_percentage": LIMIT_OFFSET_BUY,
                                    "description": desc}
                sms_message_body = f"aSentrX: BUY order triggered for {TRADE_SYMBOL} (High Conf UP). Amount: {ORDER_AMOUNT_BUY_HIGH_CONF}"
            elif confidence >= 0.8:
                desc = "Medium-Confidence UP"
                logger.info(f"{log_prefix} ACTION: {desc}. Preparing BUY order.")
                logfire.info(f"{log_prefix} ACTION: {desc}. Preparing BUY order.")
                order_to_execute = {"amount": ORDER_AMOUNT_BUY_MED_CONF, "limit_offset_percentage": LIMIT_OFFSET_BUY,
                                    "description": desc}
                sms_message_body = f"aSentrX: BUY order triggered for {TRADE_SYMBOL} (Med Conf UP). Amount: {ORDER_AMOUNT_BUY_MED_CONF}"
            else:
                logger.info(f"{log_prefix} Predicted UP, but confidence ({confidence:.2f}) is below 0.8. No action.")

        elif direction_lower == "down":
            if confidence >= 0.9:
                desc = "High-Confidence DOWN"
                logger.info(f"{log_prefix} ACTION: {desc}. Preparing SELL order.")
                logfire.info(f"{log_prefix} ACTION: {desc}. Preparing SELL order.")
                order_to_execute = {"amount": ORDER_AMOUNT_SELL_HIGH_CONF, "limit_offset_percentage": LIMIT_OFFSET_SELL,
                                    "description": desc}
                sms_message_body = f"aSentrX: SELL order triggered for {TRADE_SYMBOL} (High Conf DOWN). Amount: {ORDER_AMOUNT_SELL_HIGH_CONF}"
            elif confidence >= 0.8:
                desc = "Medium-Confidence DOWN"
                logger.info(f"{log_prefix} ACTION: {desc}. Preparing SELL order.")
                logfire.info(f"{log_prefix} ACTION: {desc}. Preparing SELL order.")
                order_to_execute = {"amount": ORDER_AMOUNT_SELL_MED_CONF, "limit_offset_percentage": LIMIT_OFFSET_SELL,
                                    "description": desc}
                sms_message_body = f"aSentrX: SELL order triggered for {TRADE_SYMBOL} (Med Conf DOWN). Amount: {ORDER_AMOUNT_SELL_MED_CONF}"
            else:
                logger.info(f"{log_prefix} Predicted DOWN, but confidence ({confidence:.2f}) is below 0.8. No action.")

        elif direction_lower == "neutral":
            logger.info(f"{log_prefix} Predicted NEUTRAL. No action.")
        else:
            logger.warning(f"{log_prefix} Unknown price direction '{direction_lower}'. No action.")

        if order_to_execute:
            logger.info(
                f"{log_prefix} Attempting to execute {order_to_execute['description']} order. "
                f"Amount: {order_to_execute['amount']}, Leverage: {ORDER_LEVERAGE}, "
                f"Limit Offset: {order_to_execute['limit_offset_percentage'] * 100:.2f}%"
            )
            order_executed_successfully = False
            try:
                # The execute_order method in Trader already prints success/failure and returns the result
                order_result = self.my_trader.execute_order(
                    symbol=TRADE_SYMBOL,
                    amount=order_to_execute["amount"],
                    leverage=ORDER_LEVERAGE,
                    limit_offset_percentage=order_to_execute["limit_offset_percentage"]
                )
                if order_result:  # Check if order_result indicates success (not None or empty)
                    order_executed_successfully = True
                    # Note: Trader.execute_order already prints "Order submission successful..."
            except Exception as e:
                logger.error(
                    f"{log_prefix} EXCEPTION during order execution for {order_to_execute['description']}: {e}",
                    exc_info=True)

            # --- Send SMS Notification if order was attempted and SMS is enabled ---
            if sms_message_body and self.sms_notifier:
                final_sms_body = f"{sms_message_body}. Status: {'Succeeded' if order_executed_successfully else 'Failed or Aborted'}."
                self.sms_notifier.send_sms(final_sms_body)
            elif sms_message_body and not self.sms_notifier:
                logger.debug(
                    f"Status ID [{status_id_for_log}]: SMS notification for '{sms_message_body}' was prepared, but SmsNotifier is not active.")

    def fetch_and_process_statuses(self):
        logger.debug(f"Attempting to fetch statuses for '{self.username}' since_id: {self.last_known_id or 'None'}.")

        try:
            statuses_generator = self.api.pull_statuses(
                username=self.username, replies=False, verbose=self.api_verbose_output, since_id=self.last_known_id
            )
            statuses = list(statuses_generator)
        except Exception as e:
            logger.error(f"Error during API call to fetch statuses for '{self.username}': {e}", exc_info=True)
            return

        if not statuses:
            logger.info(f"No new statuses found for '{self.username}' since id {self.last_known_id or 'None'}.")
            return

        for status_dict in reversed(statuses):
            status_string = str(status_dict)
            parser = StatusParser(status_string)

            if not parser.is_valid():
                logger.warning(f"Failed to parse a status. Parser Error: {parser.parse_error}. "
                               f"Problematic raw data snippet (first 100 chars): {status_string[:100]}...")
                continue

            status_id = parser.id
            created_at = parser.created_at
            content_cleaned = parser.get_content(clean_html=True)
            account_username = parser.account_username
            content_preview = content_cleaned.replace('\n', ' ').replace('\r', '')[:150] if content_cleaned else "N/A"

            logger.info(
                f"New Status Parsed: ID={status_id}, CreatedAt='{created_at}', "
                f"User='{account_username or 'N/A'}', "
                f"ContentSnippet (cleaned): \"{content_preview}...\""
            )

            if content_cleaned and content_cleaned.strip():
                logger.debug(f"Status ID [{status_id}]: Analyzing content...")
                analysis_result = self.content_analyzer.analyze_content(content_cleaned,
                                                                        status_id_for_logging=status_id)

                topic_conf_str = f"{analysis_result.topic_confidence:.2f}" if analysis_result.topic_confidence is not None else "N/A"
                price_conf_str = f"{analysis_result.price_confidence:.2f}" if analysis_result.price_confidence is not None else "N/A"
                topic_classification_str = analysis_result.topic_classification if analysis_result.topic_classification is not None else "N/A"
                price_direction_str = analysis_result.price_direction if analysis_result.price_direction is not None else "N/A"

                logger.info(
                    f"Status ID [{status_id}] AI Analysis Result: "
                    f"Topic='{topic_classification_str}' (Conf: {topic_conf_str}), "
                    f"Direction='{price_direction_str}' (Conf: {price_conf_str})"
                )

                if PROD_EXECUTION_ENABLED and self.my_trader:
                    self._execute_trade_logic(analysis_result, status_id_for_log=status_id)
                elif PROD_EXECUTION_ENABLED and not self.my_trader:
                    logger.warning(
                        f"Status ID [{status_id}]: PROD_EXECUTION is True, but trader is not initialized. Trading actions will be skipped.")
            else:
                logger.debug(
                    f"Status ID [{status_id}] has no text content after cleaning. Skipping AI analysis and trading.")

        if statuses:
            potential_newest_id = statuses[0].get('id')
            if potential_newest_id:
                try:
                    current_last_id_int = int(self.last_known_id) if self.last_known_id else 0
                    potential_newest_id_int = int(potential_newest_id)
                    is_newer = potential_newest_id_int > current_last_id_int
                except (ValueError, TypeError):
                    is_newer = self.last_known_id is None or potential_newest_id > self.last_known_id
                    logger.debug(
                        f"Could not compare status IDs ({self.last_known_id}, {potential_newest_id}) numerically, used string/None comparison.")
                if is_newer:
                    logger.info(
                        f"Updating last_known_id from '{self.last_known_id or 'None'}' to '{potential_newest_id}'.")
                    self.last_known_id = potential_newest_id
                else:
                    logger.debug(
                        f"Newest ID in batch ('{potential_newest_id}') is not considered newer than current last_known_id ('{self.last_known_id or 'None'}'). Not updating.")
            else:
                logger.warning(
                    "The newest status in the fetched batch does not have an 'id' field, cannot update last_known_id.")

    def run(self, shutdown_event: threading.Event):
        logger.info(
            f"TrueSocial run loop starting for '{self.username}'. Statuses will be fetched every {self.interval_seconds} seconds.")
        try:
            while not shutdown_event.is_set():
                self.fetch_and_process_statuses()
                logger.debug(
                    f"Waiting for {self.interval_seconds} seconds before next fetch cycle for '{self.username}'...")
                shutdown_event.wait(self.interval_seconds)
        except Exception as e:
            logger.critical(f"A critical error occurred in the TrueSocial run loop for '{self.username}': {e}",
                            exc_info=True)
        finally:
            logger.info(f"TrueSocial run loop for '{self.username}' has finished.")