import ast
from bs4 import BeautifulSoup

class StatusParser:
    """
    Parses a string representation of a status dictionary and provides
    methods to access its attributes, with an option for HTML cleaning
    of the content.
    """

    def __init__(self, raw_status_string: str):
        """
        Initializes the parser with a raw string line from the status file.

        Args:
            raw_status_string (str): A string representing a Python dictionary.
                                     Example: "{'id': '123', 'content': '<p>Hi</p>'}"
        """
        self.status_data = None
        self.parse_error = None
        try:
            # Safely evaluate the string to a Python dictionary
            evaluated_data = ast.literal_eval(raw_status_string)
            if isinstance(evaluated_data, dict):
                self.status_data = evaluated_data
            else:
                self.parse_error = "Evaluated data is not a dictionary."
                print(f"Warning: Could not parse string into a dictionary. Type was: {type(evaluated_data)}")
        except (ValueError, SyntaxError, TypeError) as e:
            self.parse_error = str(e)
            print(f"Error parsing status string: {e} - problematic string (first 100 chars): {raw_status_string[:100]}...")
            self.status_data = {} # Initialize with empty dict to avoid None errors later

    def _clean_html_content(self, html_text: str) -> str:
        """
        Helper method to remove HTML tags from a given text.
        Returns the cleaned text.
        """
        if not html_text or not isinstance(html_text, str):
            return ""
        soup = BeautifulSoup(html_text, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    def get_attribute(self, attribute_name: str, default=None):
        """
        Generic method to get any attribute from the status data.

        Args:
            attribute_name (str): The name of the attribute to retrieve.
            default: The value to return if the attribute is not found.

        Returns:
            The attribute's value or the default value.
        """
        if self.status_data:
            return self.status_data.get(attribute_name, default)
        return default

    @property
    def id(self):
        """Returns the status ID, or None if not found or parse error."""
        return self.get_attribute('id')

    @property
    def created_at(self):
        """Returns the creation timestamp, or None if not found or parse error."""
        return self.get_attribute('created_at')

    def get_content(self, clean_html: bool = False) -> str | None:
        """
        Returns the content of the status.

        Args:
            clean_html (bool): If True, HTML tags will be removed from the content.
                               Defaults to False.

        Returns:
            str or None: The status content, possibly cleaned, or None if not found.
        """
        raw_content = self.get_attribute('content')
        if raw_content is None:
            return None

        if clean_html:
            return self._clean_html_content(raw_content)
        return raw_content

    @property
    def account_username(self) -> str | None:
        """
        Returns the username of the account that posted the status.
        Returns None if 'account' or 'username' is not found.
        """
        account_info = self.get_attribute('account')
        if isinstance(account_info, dict):
            return account_info.get('username')
        return None

    def is_valid(self) -> bool:
        """
        Checks if the status string was successfully parsed into a dictionary.
        """
        return self.status_data is not None and not self.parse_error and isinstance(self.status_data, dict)

    def get_raw_data(self) -> dict | None:
        """
        Returns the entire parsed status data as a dictionary.
        """
        return self.status_data