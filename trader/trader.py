from exchanges.bitfinex_trader import BitfinexTrader


class Trader:
    """
    A higher-level trading class that uses BitfinexTrader to execute orders
    based on derivative status and calculated limit prices.
    """
    # Constants for derivative status array indices (based on your example output)
    # [['tBTCF0:USTF0', MTS, None, LAST_PRICE, BID, ..., MARK_PRICE, ...]]
    # Index 0: SYMBOL
    # Index 3: LAST_PRICE
    # Index 15: MARK_PRICE (in your provided example output structure)
    # Note: Standard Bitfinex API doc for /status/deriv might list MARK_PRICE at index 9.
    # We'll use 15 based on your data, but add a check.
    DERIV_STATUS_SYMBOL_IDX = 0
    DERIV_STATUS_LAST_PRICE_IDX = 3
    DERIV_STATUS_MARK_PRICE_IDX = 15

    def __init__(self, bfx_trader: BitfinexTrader):
        """
        Initializes the Trader.

        Args:
            bfx_trader (BitfinexTrader): An instance of the BitfinexTrader class.
        """
        if not isinstance(bfx_trader, BitfinexTrader):
            raise TypeError("bfx_trader must be an instance of BitfinexTrader")
        self.bfx_trader = bfx_trader

    def execute_order(self, symbol: str, amount: float, leverage: int, limit_offset_percentage: float):
        """
        Executes a trading order.

        It first fetches the derivative status to get the current market price,
        then calculates a limit price based on the offset percentage, and finally
        submits a LIMIT order.

        Args:
            symbol (str): The trading symbol (e.g., "tBTCF0:USTF0").
            amount (float): Order amount. Positive for buy, negative for sell.
            leverage (int): The leverage for the order (e.g., 10 for 10x).
            limit_offset_percentage (float): The percentage above the current market price
                                             at which to set the limit.
                                             Example: 0.01 means 1% above market price.
                                             A positive value always means the limit price will be
                                             higher than the reference market price.

        Returns:
            The result of the order submission from BitfinexTrader, or None if an error occurs
            before submission.
        """
        print(
            f"Attempting to execute order for {symbol}: amount={amount}, lev={leverage}, offset={limit_offset_percentage * 100}%.")

        status_data_list = self.bfx_trader.get_derivative_status(symbol=symbol)

        if not status_data_list:
            print(f"Could not retrieve derivative status for {symbol}. Aborting order.")
            return None

        if not isinstance(status_data_list, list) or not status_data_list:
            print(f"Derivative status for {symbol} is empty or not in expected list format. Aborting order.")
            print(f"Received: {status_data_list}")
            return None

        # The response is a list containing one list with the actual data
        status_data = status_data_list[0]

        if not isinstance(status_data, list) or len(status_data) <= max(self.DERIV_STATUS_MARK_PRICE_IDX,
                                                                        self.DERIV_STATUS_LAST_PRICE_IDX):
            print(f"Derivative status data for {symbol} is malformed or too short. Aborting order.")
            print(f"Received inner list: {status_data}")
            return None

        mark_price_val = status_data[self.DERIV_STATUS_MARK_PRICE_IDX]
        last_price_val = status_data[self.DERIV_STATUS_LAST_PRICE_IDX]

        if mark_price_val is not None:
            current_price = float(mark_price_val)
            print(f"Using MARK_PRICE: {current_price} for {symbol}.")
        elif last_price_val is not None:
            current_price = float(last_price_val)
            print(f"Using LAST_PRICE: {current_price} for {symbol} (MARK_PRICE was None).")
        else:
            print(
                f"Could not determine current price (both MARK_PRICE and LAST_PRICE are None) for {symbol}. Aborting order.")
            return None

        # calculate limit price
        # 0.01 means limit is 1% higher/lower than the current price
        # This means the limit price will always be higher than the current market price,
        # regardless of buy or sell.
        # For a LONG order, this means you're willing to buy up to this higher price.
        # For a SHORT order, this means you're setting the limit under the current marekt price.
        if amount > 0:
            limit_price = current_price * (1 + limit_offset_percentage)
        else:
            limit_price = current_price * (1 - limit_offset_percentage)

        # Bitfinex API expects price and amount as strings
        # Format price to a reasonable number of decimal places, Bitfinex will handle precision.
        # However, for calculation, full float precision is fine. String conversion is for API.
        # Let's assume a sensible precision like 5 decimal places for price display,
        # but pass the calculated float (converted to string) to the API.
        print(
            f"Calculated limit price for {symbol}: {limit_price:.5f} (from current: {current_price:.5f} with offset: {limit_offset_percentage * 100:.2f}%)")

        # The amount should be positive for buy, negative for sell.
        # Leverage is passed as 'lev'.
        # Type is explicitly 'LIMIT'.
        order_result = self.bfx_trader.submit_order(
            symbol=symbol,
            amount=str(amount),
            price=str(limit_price),  # API requires string
            lev=leverage,
            type="LIMIT"  # Explicitly set type to LIMIT
        )

        if order_result:
            print(f"Order submission successful for {symbol}: {order_result}")
        else:
            print(f"Order submission failed for {symbol}.")

        return order_result

