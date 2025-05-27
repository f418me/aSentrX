import logging
import os
from dotenv import load_dotenv
from utils.logger_config import APP_LOGGER_NAME
from utils.sms_notifier import SmsNotifier

load_dotenv()

PROD_EXECUTION_ENABLED = os.getenv("PROD_EXECUTION", "False").lower() == "true"
SMS_NOTIFICATIONS_ENABLED = os.getenv("SMS_NOTIFICATIONS_ENABLED", "False").lower() == "true"

logger = logging.getLogger(f"{APP_LOGGER_NAME}.sms")



if SMS_NOTIFICATIONS_ENABLED:
    logger.info("SMS_NOTIFICATIONS_ENABLED is True. Initializing SmsNotifier.")
    sms_notifier = SmsNotifier()
    if not sms_notifier.client:
        logger.warning(
            "SmsNotifier initialized, but Twilio client setup failed (check logs from SmsNotifier). SMS will not be sent.")
        sms_notifier = None  # Set to None if sub-initialization failed
    sms_message_body = f"aSentrX: Test SMS"
    sms_notifier.send_sms(sms_message_body)


else:
    logger.info("SMS_NOTIFICATIONS_ENABLED is False. SmsNotifier will not be used.")

