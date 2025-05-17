import ast  # For safely evaluating a string containing a Python literal
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

# --- Example Usage ---
if __name__ == "__main__":
    # Example lines from your file (ensure they are valid Python dict strings)
    line1_str = "{'id': '114520307594338802', 'created_at': '2025-05-17T00:20:17.034Z', 'content': '<p>This is <b>bold</b> text.</p><p>Another paragraph.</p>', 'account': {'username': 'TestUser'}}"
    line2_str = "{'id': '114520015165633741', 'content': '<p><a href=\"https://example.com\">A Link</a> and some text.</p>'}"
    invalid_line_str = "{'id': 'broken" # Intentionally broken

    status_line_from_file = line1_str # Simulate reading a line

    parser = StatusParser(status_line_from_file)

    if parser.is_valid():
        print(f"Status ID: {parser.id}")
        print(f"Created At: {parser.created_at}")
        print(f"Account Username: {parser.account_username}")

        print("\nRaw Content:")
        print(parser.get_content()) # clean_html=False by default

        print("\nCleaned Content:")
        print(parser.get_content(clean_html=True))

        print("\nGetting a specific attribute (e.g., visibility):")
        print(f"Visibility: {parser.get_attribute('visibility', 'N/A')}") # Example for a key not in the minimal example

        print("\nRaw Data Dictionary:")
        # print(parser.get_raw_data()) # Uncomment to see the whole dict
    else:
        print(f"Could not parse the status line. Error: {parser.parse_error}")

    print("-" * 30)
    parser2 = StatusParser(line2_str)
    if parser2.is_valid():
        print(f"Parser 2 - ID: {parser2.id}")
        print(f"Parser 2 - Cleaned Content: {parser2.get_content(clean_html=True)}")
    else:
        print(f"Could not parse the status line for parser2. Error: {parser2.parse_error}")

    print("-" * 30)
    parser_invalid = StatusParser(invalid_line_str)
    if not parser_invalid.is_valid():
        print(f"Parser Invalid - Correctly identified as invalid. Error: {parser_invalid.parse_error}")


    # How you would use it with your file:
    # INPUT_FILENAME = "raw_statuses_dump.txt"
    # try:
    #     with open(INPUT_FILENAME, 'r', encoding='utf-8') as f:
    #         for line_number, line_content_str in enumerate(f, 1):
    #             line_content_str = line_content_str.strip()
    #             if not line_content_str: # Skip empty lines
    #                 continue
    #
    #             print(f"\n--- Processing line {line_number} ---")
    #             status_parser = StatusParser(line_content_str)
    #
    #             if status_parser.is_valid():
    #                 print(f"  ID: {status_parser.id}")
    #                 print(f"  Content (cleaned): {status_parser.get_content(clean_html=True)}")
    #                 # Access other attributes as needed
    #             else:
    #                 print(f"  Failed to parse line {line_number}. Error: {status_parser.parse_error}")
    #
    # except FileNotFoundError:
    #     print(f"Error: Input file '{INPUT_FILENAME}' not found.")
    # except Exception as e:
    #     print(f"An unexpected error occurred: {e}")