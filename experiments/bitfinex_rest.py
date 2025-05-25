from exchanges.bitfinex_trader import BitfinexTrader

if __name__ == "__main__":
    # Create a .env file in the same directory with:
    # BFX_API_KEY="your_api_key"
    # BFX_API_SECRET="your_api_secret"

    # Scenario 1: Initialize trader with default values
    print("--- Scenario 1: Trader with default values ---")
    trader_default = BitfinexTrader(
        default_symbol="tBTCF0:USTF0",
        default_order_params={"type": "LIMIT", "lev": 10}
    )

    # Authenticated calls (require valid API Keys in .env)
    if trader_default.bfx_client:  # Only execute if keys are present
        print("\nWallets:")
        wallets = trader_default.get_wallets()
        if wallets:
            for wallet in wallets:
                print(f"  Type: {wallet.wallet_type}, Currency: {wallet.currency}, Balance: {wallet.balance}")

        print("\nPositions:")
        positions = trader_default.get_positions()
        if positions:
            for pos in positions:
                print(f"  Symbol: {pos.symbol}, Amount: {pos.amount}, Base Price: {pos.base_price}")
                print(f"  pos: {pos}")

        else:
            print("  No active positions.")

        # Order with default values (symbol, type, leverage), only specify amount/price
        # Caution: This will execute a real order if keys are valid!
        # print("\nOrder with default values (symbol, type, leverage):")
        # order_result_default = trader_default.submit_order(amount="0.001", price="20000") # Example price
        # print(order_result_default)
    else:
        print("\nAuthenticated calls skipped as API key/secret are missing.")

    # Public API calls (work even without API Keys)
    print("\nDerivative Status (default symbol):")
    status_default = trader_default.get_derivative_status()
    print(status_default)

    print("\nOrder Book (default symbol):")
    order_book_default = trader_default.get_order_book()
    # print(order_book_default) # Can be very long, so only print part of it
    if order_book_default and isinstance(order_book_default, list) and len(order_book_default) > 0:
        print(f"  Order book for {trader_default.default_symbol} received, first entry: {order_book_default[0]}")
    else:
        print(f"  Could not fetch order book for {trader_default.default_symbol} or it's empty.")

    # Scenario 2: Override parameters during method call
    print("\n--- Scenario 2: Override parameters during method call ---")
    # Create a trader without a default symbol (or use the old one)
    trader_override = BitfinexTrader(default_order_params={"type": "LIMIT", "lev": 5})  # Different default leverage

    if trader_override.bfx_client:  # Only execute if keys are present
        # Order with overridden values
        # Caution: This will execute a real order if keys are valid!
        # print("\nOrder with overridden values:")
        # order_result_override = trader_override.submit_order(
        #     symbol="tETHF0:USTF0", # Overrides default_symbol (if set)
        #     amount="0.01",         # Required
        #     price="1000",          # Required, example price
        #     type="EXCHANGE LIMIT", # Overrides default_order_params['type']
        #     lev=20                 # Overrides default_order_params['lev'] and the trader's default
        # )
        # print(order_result_override)
        pass  # Commented out to prevent accidental orders
    else:
        print("\nAuthenticated order submission skipped as API key/secret are missing.")

    # Scenario 3: Trader without API Keys for purely public data
    print("\n--- Scenario 3: Trader for public data only (no API Keys) ---")
    public_trader = BitfinexTrader(default_symbol="tBTCUSD")  # Not a derivative, but spot

    print("\nDerivative Status (public trader, tBTCF0:USTF0):")  # Must pass symbol
    status_public_deriv = public_trader.get_derivative_status(symbol="tBTCF0:USTF0")
    print(status_public_deriv)

    print("\nOrder Book (public trader, default symbol tBTCUSD):")
    order_book_public_spot = public_trader.get_order_book()  # Uses default_symbol tBTCUSD
    if order_book_public_spot and isinstance(order_book_public_spot, list) and len(order_book_public_spot) > 0:
        print(f"  Order book for {public_trader.default_symbol} received, first entry: {order_book_public_spot[0]}")
    else:
        print(f"  Could not fetch order book for {public_trader.default_symbol} or it's empty.")

