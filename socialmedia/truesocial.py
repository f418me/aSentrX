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

# --- TRUTHSOCIAL AUTH CONFIGURATION ---
# If TRUTHSOCIAL_TOKEN is set, it will be used directly (skips OAuth login).
# Extract from browser: DevTools → Application → Local Storage → truthsocial.com → key 'truth:auth' → access_token
TRUTHSOCIAL_TOKEN = os.getenv("TRUTHSOCIAL_TOKEN", "").strip() or None

# --- DECODO PROXY CONFIGURATION ---
DECODO_PROXY_ENABLED = os.getenv("DECODO_PROXY_ENABLED", "False").lower() == "true"
DECODO_PROXY_URL = os.getenv("DECODO_PROXY_URL", "")
DECODO_PROXY_USERNAME = os.getenv("DECODO_PROXY_USERNAME", "")
DECODO_PROXY_PASSWORD = os.getenv("DECODO_PROXY_PASSWORD", "")
try:
    DECODO_PROXY_MAX_RETRIES = max(1, int(os.getenv("DECODO_PROXY_MAX_RETRIES", "3")))
except ValueError:
    logger.warning("Invalid DECODO_PROXY_MAX_RETRIES value. Falling back to 3.")
    DECODO_PROXY_MAX_RETRIES = 3

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
    def _sanitize_proxy_url(self, url: str) -> str:
        """
        Removes credentials (username:password) from a proxy URL for safe logging.
        
        Args:
            url: The proxy URL that may contain credentials
            
        Returns:
            The URL without credentials
        """
        import re
        # Removes username:password@ from URL (e.g. http://user:pass@host:port -> http://host:port)
        return re.sub(r'://[^:]+:[^@]+@', '://', url)

    def _build_proxy_config(self) -> dict | None:
        """
        Creates proxy configuration for truthbrush Api based on environment variables.
        
        Returns:
            dict with 'proxies' for requests library, or None if proxy is disabled or configuration is invalid
        """
        if not DECODO_PROXY_ENABLED:
            logger.debug("Decodo Proxy is disabled (DECODO_PROXY_ENABLED=False).")
            return None
        
        if not DECODO_PROXY_URL:
            logger.warning(
                "Decodo Proxy is enabled (DECODO_PROXY_ENABLED=True), but DECODO_PROXY_URL is not set. "
                "Proxy will not be used."
            )
            return None
        
        # Validate URL format (basic check)
        if not DECODO_PROXY_URL.startswith(('http://', 'https://')):
            logger.error(
                f"Invalid DECODO_PROXY_URL format: '{self._sanitize_proxy_url(DECODO_PROXY_URL)}'. "
                "URL must start with 'http://' or 'https://'. Proxy will not be used."
            )
            return None
        
        # Build proxy URL with authentication if available
        proxy_url = DECODO_PROXY_URL
        if DECODO_PROXY_USERNAME and DECODO_PROXY_PASSWORD:
            # Insert credentials into URL
            # Format: http://username:password@host:port
            protocol, rest = proxy_url.split('://', 1)
            proxy_url = f"{protocol}://{DECODO_PROXY_USERNAME}:{DECODO_PROXY_PASSWORD}@{rest}"
            logger.debug("Proxy authentication enabled (Username and Password are set).")
        elif DECODO_PROXY_USERNAME or DECODO_PROXY_PASSWORD:
            logger.warning(
                "Only one of the proxy credentials (Username or Password) is set. "
                "Both must be set for authentication. Proxy will be used without authentication."
            )
        
        # Create requests-compatible proxy dictionary
        proxy_config = {
            "proxies": {
                "http": proxy_url,
                "https": proxy_url
            }
        }
        
        logger.debug(
            f"Proxy configuration successfully created for URL: {self._sanitize_proxy_url(DECODO_PROXY_URL)}"
        )
        
        return proxy_config

    def __init__(self, username: str, fetch_interval_seconds: int, api_verbose_output: bool,
                 initial_since_id: str | None = None):
        # Build proxy configuration before Api instantiation
        proxy_config = self._build_proxy_config()
        
        # Store proxy config for later use
        self.proxy_config = proxy_config
        
        # Log authentication mode
        if TRUTHSOCIAL_TOKEN:
            logger.info("🔑 Auth mode: TRUTHSOCIAL_TOKEN (Bearer token) — OAuth login will be skipped.")
            logfire.info("Auth mode: TRUTHSOCIAL_TOKEN (Bearer token)")
        else:
            logger.info("🔑 Auth mode: Username/Password (OAuth login flow)")
            logfire.info("Auth mode: Username/Password (OAuth login flow)")
        
        # Initialize truthbrush Api with or without proxy
        self.api = None
        proxy_initialization_failed = False
        
        if proxy_config:
            sanitized_url = self._sanitize_proxy_url(DECODO_PROXY_URL)
            logger.info(f"🔧 Initializing truthbrush Api with Decodo Proxy: {sanitized_url}")
            logger.info(f"📍 Proxy will be automatically used for every request (via _make_session override)")
            
            try:
                # Initialize Api and override _make_session to inject proxy
                # Pass token explicitly so truthbrush skips OAuth login if token is available
                self.api = Api(token=TRUTHSOCIAL_TOKEN)

                # Create new _make_session that adds proxy configuration
                def _make_session_with_proxy():
                    # Try to use curl_cffi if available (truthbrush prefers it)
                    try:
                        from curl_cffi.requests import Session as CurlSession
                        s = CurlSession(proxies=proxy_config["proxies"])
                        logger.debug(f"🔄 New curl_cffi session with proxy created for IP rotation")
                        return s
                    except ImportError:
                        # Fallback to standard requests.Session
                        import requests
                        s = requests.Session()
                        s.proxies.update(proxy_config["proxies"])
                        logger.debug(f"🔄 New requests session with proxy created for IP rotation")
                        return s
                
                # Override the method
                self.api._make_session = _make_session_with_proxy
                
                logger.info(f"✅ Successfully initialized Api with proxy: {sanitized_url}")
                logger.info(f"✅ _make_session() overridden - Proxy will be used for every request")

            except ConnectionError as e:
                logger.error(
                    f"❌ Proxy connection error during Api initialization with {sanitized_url}: {e}. "
                    f"The proxy server may be unreachable. Falling back to direct connection.",
                    exc_info=True
                )
                logfire.error(f"Proxy connection failed for {sanitized_url}: {e}")
                proxy_initialization_failed = True
                self.api = None
                
                # Send SMS notification if enabled
                if SMS_NOTIFICATIONS_ENABLED:
                    try:
                        temp_sms = SmsNotifier()
                        if temp_sms.client:
                            temp_sms.send_sms(
                                f"aSentrX: Proxy connection failed ({sanitized_url}). Using direct connection."
                            )
                    except Exception as sms_error:
                        logger.debug(f"Failed to send SMS notification about proxy error: {sms_error}")
                        
            except (TimeoutError, OSError) as e:
                logger.error(
                    f"❌ Network error during Api initialization with proxy {sanitized_url}: {e}. "
                    f"Falling back to direct connection.",
                    exc_info=True
                )
                logfire.error(f"Proxy network error for {sanitized_url}: {e}")
                proxy_initialization_failed = True
                self.api = None
                
            except Exception as e:
                logger.error(
                    f"❌ Failed to configure proxy on Api: {e}. "
                    f"Falling back to direct connection.",
                    exc_info=True
                )
                logfire.error(
                    f"Proxy configuration failed for {sanitized_url}: {e}"
                )
                proxy_initialization_failed = True
                self.api = None

        # Fallback to direct connection if proxy failed or was not configured
        if self.api is None:
            if proxy_initialization_failed:
                logger.warning(
                    f"⚠️  Proxy initialization failed. Initializing truthbrush Api with direct connection as fallback."
                )
                logfire.warning("Falling back to direct connection after proxy failure")
            else:
                logger.info("ℹ️  Initializing truthbrush Api without proxy (DECODO_PROXY_ENABLED=False)")

            try:
                self.api = Api(token=TRUTHSOCIAL_TOKEN)
                logger.info("✅ Successfully initialized Api with direct connection")
            except Exception as e:
                error_message = f"CRITICAL: Failed to initialize truthbrush Api even without proxy: {e}"
                logger.error(error_message, exc_info=True)
                logfire.error(error_message)

                # In PROD mode, this is critical and should not continue
                if PROD_EXECUTION_ENABLED:
                    logger.error("PROD_EXECUTION mode: Cannot continue without Api instance. Aborting initialization.")
                    raise RuntimeError(error_message) from e
                else:
                    logger.warning("Non-PROD mode: Continuing despite Api initialization failure for testing purposes.")
                    # In non-PROD, we might want to continue for debugging, but this is risky
                    raise RuntimeError(error_message) from e

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
        
        if self.proxy_config:
            logger.info(f"Proxy Retry Configuration - Max Retries: {DECODO_PROXY_MAX_RETRIES} (with new IP on each retry)")

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

    def _check_current_ip(self) -> str | None:
        """
        Checks the current IP address used for requests.
        Uses the same proxy as the API if configured.
        
        Returns:
            The current IP address or None on error
        """
        try:
            import requests
            
            # Use the same proxy configuration as the API
            proxies = None
            if self.proxy_config:
                proxies = self.proxy_config["proxies"]
            
            response = requests.get('https://api.ipify.org?format=json', proxies=proxies, timeout=5)
            if response.status_code == 200:
                return response.json().get('ip')
        except Exception as e:
            logger.debug(f"IP check failed: {e}")
        return None

    def _is_blocked_error(self, exception: Exception) -> bool:
        """
        Checks if the exception indicates that the IP was blocked.
        
        Args:
            exception: The exception to check
            
        Returns:
            True if the error indicates IP blocking, False otherwise
        """
        error_str = str(exception).lower()
        
        # Common blocking indicators
        blocking_indicators = [
            "403",  # Forbidden
            "429",  # Too Many Requests
            "blocked",
            "rate limit",
            "access denied",
            "forbidden",
            "captcha",
            "cloudflare",
            "security check",
            "cannot authenticate",
        ]
        
        return any(indicator in error_str for indicator in blocking_indicators)

    def fetch_and_process_statuses(self):
        """
        Fetches and processes statuses with automatic retry on blocked IPs.
        If proxy is enabled and request fails due to blocking, retries with new IP.
        """
        max_retries = DECODO_PROXY_MAX_RETRIES if self.proxy_config else 1
        request_succeeded = False
        statuses = []
        
        for attempt in range(1, max_retries + 1):
            # IP-Check before request
            current_ip = self._check_current_ip()
            ip_info = f" [IP: {current_ip}]" if current_ip else ""
            
            proxy_status = "🔒 PROXY AKTIV" if self.proxy_config else "🌐 DIREKT"
            
            retry_info = f" (Attempt {attempt}/{max_retries})" if max_retries > 1 and attempt > 1 else ""
            
            logger.info(f"{'='*80}")
            logger.info(f"🔄 API REQUEST START - {proxy_status}{ip_info}{retry_info}")
            logger.info(f"   User: '{self.username}' | Since ID: {self.last_known_id or 'None'}")
            logger.info(f"{'='*80}")

            try:
                statuses_generator = self.api.pull_statuses(
                    username=self.username, replies=False, verbose=self.api_verbose_output, since_id=self.last_known_id
                )
                statuses = list(statuses_generator)  # Materialize the generator to a list
                
                # IP-Check after request
                new_ip = self._check_current_ip()
                new_ip_info = f" [IP: {new_ip}]" if new_ip else ""
                
                logger.info(f"{'='*80}")
                if current_ip and new_ip and current_ip != new_ip:
                    logger.info(f"✅ IP CHANGED: {current_ip} → {new_ip}")
                    logger.info(f"   Proxy is working correctly - IP was rotated!")
                elif current_ip and new_ip:
                    logger.warning(f"⚠️  IP UNCHANGED: {current_ip}")
                    logger.warning(f"   Proxy may not rotate IP on every request")
                    logger.warning(f"   This can be normal when requests occur in quick succession")
                
                logger.info(f"✅ API REQUEST COMPLETE{new_ip_info} - {len(statuses)} statuses fetched")
                logger.info(f"{'='*80}")
                
                # Success - break retry loop
                request_succeeded = True
                break
                
            except SystemExit as e:
                # truthbrush raises SystemExit on auth failures (e.g. HTTP 403).
                is_blocked = self._is_blocked_error(e)

                logger.error(f"{'='*80}")
                logger.error(
                    f"❌ API REQUEST FAILED - truthbrush aborted during authentication for '{self.username}': {e}",
                    exc_info=True
                )

                if is_blocked and self.proxy_config and attempt < max_retries:
                    logger.warning("🚫 Authentication appears blocked; retrying with a new proxy IP/session")
                    logger.info(f"🔄 RETRYING with new proxy IP (attempt {attempt + 1}/{max_retries})...")
                    logger.info(f"{'='*80}")
                    import time
                    time.sleep(2)
                    continue

                if is_blocked:
                    logger.error(f"❌ Max retries ({max_retries}) reached - authentication still blocked")
                else:
                    logger.error("❌ Authentication failed in truthbrush (SystemExit) and is not classified as blocking")
                logger.error(f"{'='*80}")
                return

            except Exception as e:
                is_blocked = self._is_blocked_error(e)
                
                logger.error(f"{'='*80}")
                logger.error(f"❌ API REQUEST FAILED - Error during API call to fetch statuses for '{self.username}': {e}", exc_info=True)
                
                if is_blocked:
                    logger.warning(f"🚫 IP appears to be BLOCKED (detected blocking indicators in error)")
                    
                    if self.proxy_config and attempt < max_retries:
                        logger.info(f"🔄 RETRYING with new proxy IP (attempt {attempt + 1}/{max_retries})...")
                        logger.info(f"   Forcing new session to get different IP")
                        logger.info(f"{'='*80}")
                        
                        # Force a small delay before retry to allow IP rotation
                        import time
                        time.sleep(2)
                        
                        # Continue to next attempt
                        continue
                    else:
                        if not self.proxy_config:
                            logger.error(f"❌ IP blocked but proxy is not enabled - cannot retry with new IP")
                        else:
                            logger.error(f"❌ Max retries ({max_retries}) reached - all proxy IPs appear to be blocked")
                        logger.error(f"{'='*80}")
                        return
                else:
                    logger.warning(f"⚠️  Error does not appear to be IP blocking - not retrying")
                    logger.error(f"{'='*80}")
                    return
        
        if not request_succeeded:
            logger.error(f"❌ Failed after {max_retries} attempts with different proxy IPs")
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
