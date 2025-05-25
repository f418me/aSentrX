import os
import requests
from bfxapi import Client, REST_HOST
from dotenv import load_dotenv

load_dotenv()


class BitfinexTrader:
    """
    A class to interact with the Bitfinex API for trading and fetching market data.
    """
    PUBLIC_API_BASE_URL = "https://api-pub.bitfinex.com/v2"

    def __init__(self, api_key=None, api_secret=None, default_symbol=None, default_order_params=None):
        """
        Initializes the BitfinexTrader.

        Args:
            api_key (str, optional): Your Bitfinex API key. Defaults to env BFX_API_KEY.
            api_secret (str, optional): Your Bitfinex API secret. Defaults to env BFX_API_SECRET.
            default_symbol (str, optional): Default trading symbol (e.g., "tBTCF0:USTF0").
            default_order_params (dict, optional): Default parameters for submitting orders.
                                                  Example: {"type": "LIMIT", "lev": 10}
        """
        self.api_key = api_key or os.getenv("BFX_API_KEY")
        self.api_secret = api_secret or os.getenv("BFX_API_SECRET")

        if not self.api_key or not self.api_secret:
            print("Warning: API key or secret not provided. Authenticated methods will fail.")
            self.bfx_client = None  # Kein Client, wenn keine Keys
        else:
            self.bfx_client = Client(
                rest_host=REST_HOST,
                api_key=self.api_key,
                api_secret=self.api_secret
            )

        self.default_symbol = default_symbol
        self.default_order_params = default_order_params if default_order_params else {}

    def _get_symbol(self, symbol_override=None):
        """Helper to determine which symbol to use."""
        chosen_symbol = symbol_override if symbol_override is not None else self.default_symbol
        if not chosen_symbol:
            raise ValueError("Symbol must be provided either as default or method argument.")
        return chosen_symbol

    def _get_client(self):
        """Helper to get the authenticated client, raises error if not available."""
        if not self.bfx_client:
            raise ConnectionError("Authenticated Bitfinex client not initialized. API Key/Secret missing?")
        return self.bfx_client.rest.auth

    def get_wallets(self):
        """
        Retrieves all wallets for the authenticated user.
        """
        try:
            return self._get_client().get_wallets()
        except Exception as e:
            print(f"Error getting wallets: {e}")
            return None

    def get_positions(self):
        """
        Retrieves all active positions for the authenticated user.
        """
        try:
            return self._get_client().get_positions()
        except Exception as e:
            print(f"Error getting positions: {e}")
            return None

    def submit_order(self, amount, price, symbol=None, **order_specific_params):
        """
        Submits an order.

        Args:
            amount (str): Order amount. Positive for buy, negative for sell.
            price (str): Order price.
            symbol (str, optional): Trading symbol (e.g., "tBTCF0:USTF0").
                                    Overrides default_symbol if set.
            **order_specific_params: Additional parameters for the order,
                                     e.g., type="LIMIT", lev=10.
                                     These override default_order_params.

        Returns:
            The result of the order submission.
        """
        final_symbol = self._get_symbol(symbol)

        # Start with class default order parameters
        params_to_submit = self.default_order_params.copy()
        # Update with any parameters passed directly to the method
        params_to_submit.update(order_specific_params)

        # Add mandatory parameters
        params_to_submit['symbol'] = final_symbol
        params_to_submit['amount'] = str(amount)  # Ensure amount is string
        params_to_submit['price'] = str(price)  # Ensure price is string

        # Ensure essential parameters are present
        if 'type' not in params_to_submit:
            # Default to LIMIT if not specified anywhere
            params_to_submit['type'] = "LIMIT"
            print(f"Warning: Order type not specified, defaulting to 'LIMIT'.")

        print(f"Submitting order with params: {params_to_submit}")
        try:
            return self._get_client().submit_order(**params_to_submit)
        except Exception as e:
            print(f"Error submitting order: {e}")
            return None

    def get_derivative_status(self, symbol=None):
        """
        Fetches the status for a specific derivative symbol.

        Args:
            symbol (str, optional): The derivative symbol (e.g., "tBTCF0:USTF0").
                                    Overrides default_symbol if set.
        Returns:
            dict: The JSON response from the API or None on error.
        """
        final_symbol = self._get_symbol(symbol)
        url = f"{self.PUBLIC_API_BASE_URL}/status/deriv?keys={final_symbol}"
        headers = {"accept": "application/json"}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching derivative status for {final_symbol}: {e}")
            return None
        except ValueError:  # requests.JSONDecodeError inherits from ValueError
            print(f"Error decoding JSON response for derivative status of {final_symbol}.")
            return None

    def get_order_book(self, symbol=None, precision="P0", length=25):
        """
        Fetches the order book for a specific symbol.

        Args:
            symbol (str, optional): The trading symbol (e.g., "tBTCF0:USTF0").
                                    Overrides default_symbol if set.
            precision (str, optional): Level of price aggregation (P0, P1, P2, P3, P4).
                                       R0 for raw books. Defaults to "P0".
            length (int, optional): Number of price points ("25", "100"). Defaults to 25.

        Returns:
            dict: The JSON response from the API or None on error.
        """
        final_symbol = self._get_symbol(symbol)
        url = f"{self.PUBLIC_API_BASE_URL}/book/{final_symbol}/{precision}?len={length}"
        headers = {"accept": "application/json"}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching order book for {final_symbol}: {e}")
            return None
        except ValueError:  # requests.JSONDecodeError inherits from ValueError
            print(f"Error decoding JSON response for order book of {final_symbol}.")
            return None


