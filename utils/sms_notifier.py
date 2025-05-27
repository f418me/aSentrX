# utils/sms_notifier.py

import os
import logging
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException # Import for specific Twilio errors

# Assuming APP_LOGGER_NAME is defined in your logger_config.py
# If not, you can define a local logger name here or pass the logger instance.
# For consistency, let's assume you have APP_LOGGER_NAME accessible
# If logger_config is in the same directory (utils), you might do:
# from .logger_config import APP_LOGGER_NAME
# Or if it's one level up:
# from ..utils.logger_config import APP_LOGGER_NAME
# For now, let's define a local one if the import path is complex for this example
try:
    from utils.logger_config import APP_LOGGER_NAME # If logger_config is in the same 'utils' dir
except ImportError:
    APP_LOGGER_NAME = "SmsNotifier" # Fallback logger name

logger = logging.getLogger(f"{APP_LOGGER_NAME}.SmsNotifier")

load_dotenv()

class SmsNotifier:
    """
    A class to handle sending SMS notifications using Twilio.
    """
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')
        self.to_number = os.getenv('TWILIO_TO_NUMBER')

        if not all([self.account_sid, self.auth_token, self.from_number, self.to_number]):
            logger.warning(
                "Twilio credentials or phone numbers are not fully configured in .env. "
                "SMS notifications will be disabled."
            )
            self.client = None
        else:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized successfully for SMS notifications.")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}", exc_info=True)
                self.client = None

    def send_sms(self, body: str) -> str | None:
        """
        Sends an SMS message.

        Args:
            body (str): The content of the SMS message.

        Returns:
            str | None: The message SID if successful, None otherwise.
        """
        if not self.client:
            logger.warning("Twilio client not initialized. Cannot send SMS.")
            return None

        if not body:
            logger.warning("SMS body is empty. Cannot send SMS.")
            return None

        try:
            message = self.client.messages.create(
                from_=self.from_number,
                body=body,
                to=self.to_number
            )
            logger.info(f"SMS sent successfully to {self.to_number}. Message SID: {message.sid}")
            return message.sid
        except TwilioRestException as e: # Catch specific Twilio errors
            logger.error(f"Twilio API error while sending SMS to {self.to_number}: {e}", exc_info=True)
            return None
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error while sending SMS to {self.to_number}: {e}", exc_info=True)
            return None
