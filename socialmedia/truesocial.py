import logging
import threading
from truthbrush import Api
from utils import StatusParser
from ai.asentrx_agent import ContentAnalyzer
from utils.logger_config import APP_LOGGER_NAME


logger = logging.getLogger(f"{APP_LOGGER_NAME}.TrueSocial")


class TrueSocial:
    """
    Main class for the TrueSocial application.
    Handles fetching, parsing, and logging socialtrue  statuses periodically.
    """
    def __init__(self, username: str, fetch_interval_seconds: int, api_verbose_output: bool, initial_since_id: str | None = None):
        self.api = Api()
        self.username = username
        self.last_known_id = initial_since_id
        self.interval_seconds = fetch_interval_seconds
        self.api_verbose_output = api_verbose_output

        logger.info(f"ASentrX instance initialized for user: '{self.username}'. "
                           f"Initial since_id: {self.last_known_id or 'None'}.")

        logger.debug(f"Instance configuration - Fetch interval: {fetch_interval_seconds}s. "
                            f"Truthbrush API Verbose: {self.api_verbose_output}.")

    def fetch_and_process_statuses(self):
        """
        Fetches new statuses since the last_known_id, processes them using StatusParser,
        logs relevant information, and updates the last_known_id.
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

        for status_dict in reversed(statuses):
            status_string = str(status_dict)
            parser = StatusParser(status_string)

            if parser.is_valid():
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
                    content_analyzer = ContentAnalyzer()
                    content_analyzer.analyze_content(content_cleaned)
                    logger.debug(
                        f"AI agent invocation for status ID {status_id}.")
                else:
                    logger.debug(f"Status ID {status_id} has no text content. Skipping AI agent.")
            else:
                logger.warning(f"Failed to parse a status. Parser Error: {parser.parse_error}. "
                                      f"Problematic raw data snippet (first 100 chars): {status_string[:100]}...")

        if statuses:
            potential_newest_id = statuses[0].get('id')
            if potential_newest_id:
                try:
                    is_newer = self.last_known_id is None or \
                               (isinstance(self.last_known_id, str) and int(potential_newest_id) > int(self.last_known_id))
                except (ValueError, TypeError):
                    is_newer = self.last_known_id is None or potential_newest_id > self.last_known_id
                    logger.debug(f"Could not compare status IDs ({self.last_known_id}, {potential_newest_id}) numerically, used string comparison.")

                if is_newer:
                    logger.info(f"Updating last_known_id from '{self.last_known_id or 'None'}' to '{potential_newest_id}'.")
                    self.last_known_id = potential_newest_id
                else:
                    logger.debug(f"Newest ID in batch ('{potential_newest_id}') is not considered newer than "
                                        f"current last_known_id ('{self.last_known_id or 'None'}'). Not updating.")
            else:
                logger.warning("The newest status in the fetched batch does not have an 'id' field, cannot update last_known_id.")

    def run(self, shutdown_event: threading.Event):
        """
        Main operational loop for the application.
        Periodically calls fetch_and_process_statuses().
        The loop continues until the global shutdown_event is set.
        """
        logger.info(f"ASentrX run loop starting for '{self.username}'. Statuses will be fetched every {self.interval_seconds} seconds.")

        try:
            while not shutdown_event.is_set():
                self.fetch_and_process_statuses()
                logger.debug(f"Waiting for {self.interval_seconds} seconds before next fetch cycle for '{self.username}'...")
                shutdown_event.wait(self.interval_seconds)
        except Exception as e:
            logger.critical(f"A critical error occurred in the ASentrX run loop for '{self.username}': {e}", exc_info=True)

        finally:
            logger.info(f"ASentrX run loop for '{self.username}' has finished.")

# --- END OF FILE socialmedia/asentrx_service.py ---