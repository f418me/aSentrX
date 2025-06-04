import logging
import os
import sys
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

TRADE_SYMBOL = os.getenv("TRADE_SYMBOL", "tBTCF0:USTF0")

# --- GENERIC ORDER AMOUNTS (Positive for BUY/LONG, Negative for SHORT) ---
ORDER_AMOUNT_BUY_HIGH_CONF = float(os.getenv("ORDER_AMOUNT_BUY_HIGH_CONF", "0.001"))
ORDER_AMOUNT_SHORT_HIGH_CONF = float(os.getenv("ORDER_AMOUNT_SHORT_HIGH_CONF", "-0.001"))
ORDER_AMOUNT_BUY_MED_CONF = float(os.getenv("ORDER_AMOUNT_BUY_MED_CONF", "0.0005"))
ORDER_AMOUNT_SHORT_MED_CONF = float(os.getenv("ORDER_AMOUNT_SHORT_MED_CONF", "-0.0005"))

# --- GENERIC LEVERAGE SETTINGS ---
LEVERAGE_BUY_HIGH_CONF = int(os.getenv("LEVERAGE_BUY_HIGH_CONF", "10"))
LEVERAGE_SHORT_HIGH_CONF = int(os.getenv("LEVERAGE_SHORT_HIGH_CONF", "10"))
LEVERAGE_BUY_MED_CONF = int(os.getenv("LEVERAGE_BUY_MED_CONF", "5"))
LEVERAGE_SHORT_MED_CONF = int(os.getenv("LEVERAGE_SHORT_MED_CONF", "5"))

# --- BITCOIN SPECIFIC ORDER AMOUNTS (Positive for BUY/LONG, Negative for SHORT) ---
# These will be used when the AI topic classification is "bitcoin"
ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF = float(os.getenv("ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF", "0.0015")) # e.g., slightly higher
ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF = float(os.getenv("ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF", "-0.0015"))
ORDER_AMOUNT_BITCOIN_BUY_MED_CONF = float(os.getenv("ORDER_AMOUNT_BITCOIN_BUY_MED_CONF", "0.00075"))
ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF = float(os.getenv("ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF", "-0.00075"))

# --- BITCOIN SPECIFIC LEVERAGE SETTINGS ---
LEVERAGE_BITCOIN_BUY_HIGH_CONF = int(os.getenv("LEVERAGE_BITCOIN_BUY_HIGH_CONF", "15")) # e.g., slightly higher
LEVERAGE_BITCOIN_SHORT_HIGH_CONF = int(os.getenv("LEVERAGE_BITCOIN_SHORT_HIGH_CONF", "15"))
LEVERAGE_BITCOIN_BUY_MED_CONF = int(os.getenv("LEVERAGE_BITCOIN_BUY_MED_CONF", "7"))
LEVERAGE_BITCOIN_SHORT_MED_CONF = int(os.getenv("LEVERAGE_BITCOIN_SHORT_MED_CONF", "7"))

# --- GENERIC CONFIDENCE THRESHOLDS FOR TRADING ---
CONFIDENCE_THRESHOLD_HIGH = float(os.getenv("CONFIDENCE_THRESHOLD_HIGH", "0.95"))
CONFIDENCE_THRESHOLD_MED = float(os.getenv("CONFIDENCE_THRESHOLD_MED", "0.9"))

# --- BITCOIN SPECIFIC CONFIDENCE THRESHOLDS FOR TRADING ---
CONFIDENCE_THRESHOLD_BITCOIN_HIGH = float(os.getenv("CONFIDENCE_THRESHOLD_BITCOIN_HIGH", "0.93")) # e.g., slightly lower to trigger more often
CONFIDENCE_THRESHOLD_BITCOIN_MED = float(os.getenv("CONFIDENCE_THRESHOLD_BITCOIN_MED", "0.88"))

# Trader class applies: BUY_LIMIT = PRICE * (1 + OFFSET), SHORT_LIMIT = PRICE * (1 - OFFSET)
LIMIT_OFFSET_BUY = float(os.getenv("LIMIT_OFFSET_BUY", "0.005"))
LIMIT_OFFSET_SHORT = float(os.getenv("LIMIT_OFFSET_SHORT", "0.005"))


class TrueSocial:
    def __init__(self, username: str, fetch_interval_seconds: int, api_verbose_output: bool,
                 initial_since_id: str | None = None):
        self.api = Api()
        self.username = username
        self.interval_seconds = fetch_interval_seconds
        self.api_verbose_output = api_verbose_output
        self.content_analyzer = ContentAnalyzer()

        if PROD_EXECUTION_ENABLED:
            logger.info(
                f"PROD_EXECUTION is enabled.. Attempting to fetch current latest status ID "
                f"to process only posts made after application startup.")
            try:
                # Pull_statuses without since_id fetches the latest ones.
                # We only need the ID of the very latest status.
                statuses_gen = self.api.pull_statuses(
                    username=self.username,
                    replies=False,
                    since_id=initial_since_id,
                    verbose=self.api_verbose_output
                )
                # Get a list from generator and take the first item
                # Truthbrush's pull_statuses yields newest items first.
                statuses_list = list(statuses_gen)
                latest_status = statuses_list[0]

                if latest_status and 'id' in latest_status:
                    self.last_known_id = str(latest_status['id'])  # Ensure it's a string
                    logger.info(f"PROD: Successfully set last_known_id to '{self.last_known_id}' "
                                f"(ID of the latest status at startup for '{self.username}'). "
                                f"Only posts strictly newer than this will be processed.")
                elif latest_status is None:  # No posts found for this user
                    error_message = (f"PROD: CRITICAL - No existing statuses found for user '{self.username}'. "
                                     f"Cannot reliably determine a starting point. Aborting initialization.")
                    logger.error(error_message)
                    logfire.error(error_message)
                    raise RuntimeError(error_message)
                else:  # Status exists but has no ID (latest_status is not None, but 'id' not in latest_status)
                    error_message = (
                        f"PROD: CRITICAL - Fetched latest status for '{self.username}' but it has no 'id' attribute. "
                        f"This is unexpected. Cannot reliably determine a starting point. Aborting initialization.")
                    logger.error(error_message)
                    logfire.error(error_message)
                    raise RuntimeError(error_message)
            except RuntimeError as e:
                error_message = (f"Initialization failed for user '{self.username}': {e}")
                logger.error(error_message)
                logfire.error(error_message)
                sys.exit(1)
            except Exception as e:
                error_message = (f"PROD: An unexpected error occurred while trying to set last_known_id for '{self.username}': {e}")
                logger.error(error_message)
                logfire.error(error_message)
                sys.exit(1)

            logger.info("PROD_EXECUTION is enabled. Attempting to initialize Bitfinex Trader.")
            self.my_trader: Trader | None = None
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
        else:  # PROD_EXECUTION is False
            self.last_known_id = initial_since_id
            logger.info(f"PROD_EXECUTION is disabled for '{self.username}'. "
                        f"Using initial_since_id from .env: '{self.last_known_id or 'None'}'.")


        self.sms_notifier: SmsNotifier | None = None
        if SMS_NOTIFICATIONS_ENABLED:
            logger.info("SMS_NOTIFICATIONS_ENABLED is True. Initializing SmsNotifier.")
            self.sms_notifier = SmsNotifier()
            if not self.sms_notifier.client:  # Assuming client attribute indicates success
                logger.warning(
                    "SmsNotifier initialized, but Twilio client setup failed (check logs from SmsNotifier). SMS will not be sent.")
                self.sms_notifier = None  # Ensure it's None if setup failed
        else:
            logger.info("SMS_NOTIFICATIONS_ENABLED is False. SmsNotifier will not be used.")

        logger.info(f"TrueSocial instance initialized for user: '{self.username}'. "
                    f"Effective initial since_id: {self.last_known_id or 'None'}.")
        logger.debug(f"Instance configuration - Fetch interval: {fetch_interval_seconds}s. "
                     f"Truthbrush API Verbose: {self.api_verbose_output}.")
        logger.info(f"Trading Configuration - TRADE_SYMBOL: {TRADE_SYMBOL}")

        logger.info(
            f"Generic Order Amounts - BUY_HIGH_CONF: {ORDER_AMOUNT_BUY_HIGH_CONF}, SHORT_HIGH_CONF: {ORDER_AMOUNT_SHORT_HIGH_CONF}, "
            f"BUY_MED_CONF: {ORDER_AMOUNT_BUY_MED_CONF}, SHORT_MED_CONF: {ORDER_AMOUNT_SHORT_MED_CONF}")
        logger.info(
            f"Generic Leverage Settings - BUY_HIGH_CONF: {LEVERAGE_BUY_HIGH_CONF}, SHORT_HIGH_CONF: {LEVERAGE_SHORT_HIGH_CONF}, "
            f"BUY_MED_CONF: {LEVERAGE_BUY_MED_CONF}, SHORT_MED_CONF: {LEVERAGE_SHORT_MED_CONF}")
        logger.info(
            f"Generic Confidence Thresholds - HIGH: {CONFIDENCE_THRESHOLD_HIGH}, MED: {CONFIDENCE_THRESHOLD_MED}")

        logger.info(
            f"Bitcoin Specific Order Amounts - BUY_HIGH_CONF: {ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF}, SHORT_HIGH_CONF: {ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF}, "
            f"BUY_MED_CONF: {ORDER_AMOUNT_BITCOIN_BUY_MED_CONF}, SHORT_MED_CONF: {ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF}")
        logger.info(
            f"Bitcoin Specific Leverage Settings - BUY_HIGH_CONF: {LEVERAGE_BITCOIN_BUY_HIGH_CONF}, SHORT_HIGH_CONF: {LEVERAGE_BITCOIN_SHORT_HIGH_CONF}, "
            f"BUY_MED_CONF: {LEVERAGE_BITCOIN_BUY_MED_CONF}, SHORT_MED_CONF: {LEVERAGE_BITCOIN_SHORT_MED_CONF}")
        logger.info(
            f"Bitcoin Specific Confidence Thresholds - HIGH: {CONFIDENCE_THRESHOLD_BITCOIN_HIGH}, MED: {CONFIDENCE_THRESHOLD_BITCOIN_MED}")

        logger.info(f"Limit Offsets - BUY: {LIMIT_OFFSET_BUY * 100:.2f}%, SHORT: {LIMIT_OFFSET_SHORT * 100:.2f}%")

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
            logfire.info(
                f"Status ID [{status_id_for_log}]: Incomplete analysis data for trading. "
                f"Topic='{topic_str}' (TopicConf: {topic_confidence_str}), "
                f"Direction='{direction_str}' (PriceConf: {confidence_str}). No trading action."
            )
            return

        topic_lower = topic.lower()
        direction_lower = direction.lower()  # "up", "down", "neutral"
        log_prefix = f"Status ID [{status_id_for_log}] Topic [{topic_lower}] Direction [{direction_lower}] Confidence [{confidence:.2f}]:"

        if topic_lower not in ["bitcoin", "market", "tariffs"]:
            logger.info(f"{log_prefix} Topic not relevant for automated trading ('{topic_lower}'). No action.")
            logfire.info(f"{log_prefix} Topic not relevant for automated trading ('{topic_lower}'). No action.")
            return

        order_to_execute = None
        sms_message_body = None

        # Determine which set of settings to use based on topic
        if topic_lower == "bitcoin":
            logger.debug(f"{log_prefix} Using Bitcoin-specific trade settings.")
            amount_buy_high = ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF
            amount_short_high = ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF
            amount_buy_med = ORDER_AMOUNT_BITCOIN_BUY_MED_CONF
            amount_short_med = ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF
            leverage_buy_high = LEVERAGE_BITCOIN_BUY_HIGH_CONF
            leverage_short_high = LEVERAGE_BITCOIN_SHORT_HIGH_CONF
            leverage_buy_med = LEVERAGE_BITCOIN_BUY_MED_CONF
            leverage_short_med = LEVERAGE_BITCOIN_SHORT_MED_CONF
            # NEW: Bitcoin-specific confidence thresholds
            confidence_threshold_high_current = CONFIDENCE_THRESHOLD_BITCOIN_HIGH
            confidence_threshold_med_current = CONFIDENCE_THRESHOLD_BITCOIN_MED
        else: # For "market", "tariffs", or any other relevant non-bitcoin topic
            logger.debug(f"{log_prefix} Using generic trade settings.")
            amount_buy_high = ORDER_AMOUNT_BUY_HIGH_CONF
            amount_short_high = ORDER_AMOUNT_SHORT_HIGH_CONF
            amount_buy_med = ORDER_AMOUNT_BUY_MED_CONF
            amount_short_med = ORDER_AMOUNT_SHORT_MED_CONF
            leverage_buy_high = LEVERAGE_BUY_HIGH_CONF
            leverage_short_high = LEVERAGE_SHORT_HIGH_CONF
            leverage_buy_med = LEVERAGE_BUY_MED_CONF
            leverage_short_med = LEVERAGE_SHORT_MED_CONF
            # NEW: Generic confidence thresholds
            confidence_threshold_high_current = CONFIDENCE_THRESHOLD_HIGH
            confidence_threshold_med_current = CONFIDENCE_THRESHOLD_MED


        # Decision logic for BUY (LONG) or SHORT
        # "up" direction from AI means we expect price to rise -> BUY/LONG
        # "down" direction from AI means we expect price to fall -> SHORT
        if direction_lower == "up":  # Potential BUY/LONG signal
            trade_action_desc_prefix = "BUY"
            # Use current (topic-specific) confidence thresholds
            if confidence >= confidence_threshold_high_current:
                desc_suffix = "High-Confidence UP"
                current_amount = amount_buy_high
                current_leverage = leverage_buy_high
                limit_offset = LIMIT_OFFSET_BUY
            elif confidence >= confidence_threshold_med_current:
                desc_suffix = "Medium-Confidence UP"
                current_amount = amount_buy_med
                current_leverage = leverage_buy_med
                limit_offset = LIMIT_OFFSET_BUY
            else:
                logger.info(
                    f"{log_prefix} Predicted UP, but confidence ({confidence:.2f}) is below {confidence_threshold_med_current} for a BUY. No action.")
                return

            if current_amount is not None and current_leverage is not None:
                full_desc = f"{trade_action_desc_prefix} ({desc_suffix})"
                logger.info(f"{log_prefix} ACTION: {full_desc}. Preparing order.")
                logfire.info(f"{log_prefix} ACTION: {full_desc}. Preparing order.")
                order_to_execute = {
                    "amount": current_amount,
                    "limit_offset_percentage": limit_offset,
                    "leverage": current_leverage,
                    "description": full_desc
                }
                sms_message_body = f"aSentrX: {full_desc} for {TRADE_SYMBOL}. Amt: {current_amount}, Lev: {current_leverage}"


        elif direction_lower == "down":
            trade_action_desc_prefix = "SHORT"
            # Use current (topic-specific) confidence thresholds
            if confidence >= confidence_threshold_high_current:
                desc_suffix = "High-Confidence DOWN"
                current_amount = amount_short_high
                current_leverage = leverage_short_high
                limit_offset = LIMIT_OFFSET_SHORT
            elif confidence >= confidence_threshold_med_current:
                desc_suffix = "Medium-Confidence DOWN"
                current_amount = amount_short_med
                current_leverage = leverage_short_med
                limit_offset = LIMIT_OFFSET_SHORT
            else:
                logger.info(
                    f"{log_prefix} Predicted DOWN, but confidence ({confidence:.2f}) is below {confidence_threshold_med_current} for a SHORT. No action.")
                return

            if current_amount is not None and current_leverage is not None:
                full_desc = f"{trade_action_desc_prefix} ({desc_suffix})"
                logger.info(f"{log_prefix} ACTION: {full_desc}. Preparing order.")
                logfire.info(f"{log_prefix} ACTION: {full_desc}. Preparing order.")
                order_to_execute = {
                    "amount": current_amount,
                    "limit_offset_percentage": limit_offset,
                    "leverage": current_leverage,
                    "description": full_desc
                }
                sms_message_body = f"aSentrX: {full_desc} for {TRADE_SYMBOL}. Amt: {current_amount}, Lev: {current_leverage}"

        elif direction_lower == "neutral":
            logger.info(f"{log_prefix} Predicted NEUTRAL. No action.")
            logfire.info(f"{log_prefix} Predicted NEUTRAL. No action.")

        else:
            logger.warning(f"{log_prefix} Unknown price direction '{direction_lower}'. No action.")

        if order_to_execute:
            logger.info(
                f"{log_prefix} Attempting to execute {order_to_execute['description']} order. "
                f"Amount: {order_to_execute['amount']}, Leverage: {order_to_execute['leverage']}, "
                f"Limit Offset: {order_to_execute['limit_offset_percentage'] * 100:.2f}%"
            )
            logfire.info(
                f"{log_prefix} Attempting to execute {order_to_execute['description']} order. "
                f"Amount: {order_to_execute['amount']}, Leverage: {order_to_execute['leverage']}, "
                f"Limit Offset: {order_to_execute['limit_offset_percentage'] * 100:.2f}%"
            )
            order_executed_successfully = False
            try:
                order_result = self.my_trader.execute_order(
                    symbol=TRADE_SYMBOL,
                    amount=order_to_execute["amount"],
                    leverage=order_to_execute["leverage"],
                    limit_offset_percentage=order_to_execute["limit_offset_percentage"]
                )
                if order_result:  # Assuming execute_order returns something truthy on success
                    order_executed_successfully = True
            except Exception as e:
                logger.error(
                    f"{log_prefix} EXCEPTION during order execution for {order_to_execute['description']}: {e}",
                    exc_info=True)

            if sms_message_body and self.sms_notifier:
                final_sms_body = f"{sms_message_body}. Status: {'Succeeded' if order_executed_successfully else 'Failed/Aborted'}."
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
            statuses = list(statuses_generator)  # Materialize the generator to a list
        except Exception as e:
            logger.error(f"Error during API call to fetch statuses for '{self.username}': {e}", exc_info=True)
            return

        if not statuses:
            logger.info(f"No new statuses found for '{self.username}' since id {self.last_known_id or 'None'}.")
            return

        # Process statuses from oldest to newest within the batch
        # truthbrush.Api.pull_statuses yields newest first. reversed() processes oldest first from the batch.
        for status_dict in reversed(statuses):
            status_string = str(status_dict)  # Assuming status_dict can be stringified
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

        # Update last_known_id to the ID of the newest status in the fetched batch
        # statuses[0] is the newest because truthbrush returns newest first from the API.
        if statuses:  # Ensure statuses list is not empty
            potential_newest_status_dict = statuses[0]  # This is a dict representing the newest status in the batch
            if isinstance(potential_newest_status_dict, dict) and 'id' in potential_newest_status_dict:
                potential_newest_id = str(potential_newest_status_dict['id'])  # Ensure it's a string

                is_newer = False
                if self.last_known_id is None:
                    is_newer = True  # Any ID is newer than None
                else:
                    # Standard Mastodon IDs are strings and can be compared lexicographically for recency
                    # (they are snowflake-like IDs, generally increasing).
                    # Numeric comparison could be an option if IDs were purely numeric and sequential.
                    try:
                        # Attempt numeric comparison if possible (e.g. if they are truly large integers)
                        current_last_id_int = int(self.last_known_id)
                        potential_newest_id_int = int(potential_newest_id)
                        if potential_newest_id_int > current_last_id_int:
                            is_newer = True
                    except ValueError:
                        # Fallback to string comparison, which is generally reliable for Mastodon IDs
                        if potential_newest_id > self.last_known_id:
                            is_newer = True

                if is_newer:
                    logger.info(
                        f"Updating last_known_id from '{self.last_known_id or 'None'}' to '{potential_newest_id}'.")
                    self.last_known_id = potential_newest_id
                else:
                    logger.debug(
                        f"Newest ID in batch ('{potential_newest_id}') is not considered newer than current last_known_id "
                        f"('{self.last_known_id or 'None'}'). Not updating last_known_id.")
            else:
                logger.warning(
                    "The newest status in the fetched batch is malformed or does not have an 'id' field. "
                    "Cannot update last_known_id from this batch.")

    def run(self, shutdown_event: threading.Event):
        logger.info(
            f"TrueSocial run loop starting for '{self.username}'. Statuses will be fetched every {self.interval_seconds} seconds.")
        try:
            while not shutdown_event.is_set():
                self.fetch_and_process_statuses()
                logger.debug(
                    f"Waiting for {self.interval_seconds} seconds before next fetch cycle for '{self.username}'...")
                # shutdown_event.wait() will return True if the event is set before the timeout, False otherwise.
                # This allows for quicker shutdown if interval_seconds is long.
                if shutdown_event.wait(self.interval_seconds):
                    break  # Event was set, exit loop
        except Exception as e:  # Catch any unexpected error in the main processing loop
            logger.critical(f"A critical error occurred in the TrueSocial run loop for '{self.username}': {e}",
                            exc_info=True)
        finally:
            logger.info(f"TrueSocial run loop for '{self.username}' has finished.")