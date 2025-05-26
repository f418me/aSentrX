from exchanges.bitfinex_trader import BitfinexTrader
from trader.trader import Trader

if __name__ == '__main__':
    # --- Example Usage ---
    # Ensure you have a .env file with BFX_API_KEY and BFX_API_SECRET
    # or pass them directly to BitfinexTrader constructor.

    # Initialize BitfinexTrader (it will load keys from .env by default)
    # You can also set default symbol or order params here if needed
    bfx_wrapper = BitfinexTrader(default_symbol="tBTCF0:USTF0")
    # default_order_params={"lev": 5}) # Example default leverage

    # Initialize our high-level Trader
    my_trader = Trader(bfx_trader=bfx_wrapper)

    # --- Define order parameters ---
    trade_symbol = "tBTCF0:USTF0"  # Example derivative symbol for Bitfinex (BTC perpetual future)

    # Example 1: Buy 0.01 BTC perpetual future
    order_amount_buy = 0.001
    order_leverage = 10  # 10x leverage
    # Set limit price 0.5% above current market price
    # (e.g., if market is 100000, limit will be 100500)
    limit_offset_buy = 0.005

    print(f"\n--- Test Case 1: BUY Order ---")
    # Execute the buy order
    # Note: This will actually attempt to place an order if API keys are valid!
    # Use with caution or on a testnet if available and supported by the library.
    # For now, we'll just print what would happen if API keys are missing.
    if bfx_wrapper.bfx_client:  # Only try if client could be initialized
        buy_order_status = my_trader.execute_order(
            symbol=trade_symbol,
            amount=order_amount_buy,
            leverage=order_leverage,
            limit_offset_percentage=limit_offset_buy
        )
        if buy_order_status:
            print(f"Buy order executed. Status: {buy_order_status}")
        else:
            print(f"Buy order execution failed or was aborted.")
    else:
        print("Bitfinex client not initialized (API keys likely missing). Skipping live order execution.")

    # Example 2: Sell 0.01 BTC perpetual future (short)
    order_amount_sell = -0.0005
    # Set limit price 0.3% above current market price
    # If current is 100000, limit will be 100300. For a sell limit, this means you want to sell at 100300 or higher.
    limit_offset_sell = 0.003

    print(f"\n--- Test Case 2: SELL Order ---")
    if bfx_wrapper.bfx_client:
        sell_order_status = my_trader.execute_order(
            symbol=trade_symbol,
            amount=order_amount_sell,
            leverage=order_leverage,  # Can be the same or different
            limit_offset_percentage=limit_offset_sell
        )
        if sell_order_status:
            print(f"Sell order executed. Status: {sell_order_status}")
        else:
            print(f"Sell order execution failed or was aborted.")
    else:
        print("Bitfinex client not initialized (API keys likely missing). Skipping live order execution.")

    # Example 3: Using a different symbol, if configured as default in BitfinexTrader
    # bfx_wrapper_eth = BitfinexTrader(default_symbol="tETHF0:USTF0")
    # my_eth_trader = Trader(bfx_trader=bfx_wrapper_eth)
    # my_eth_trader.execute_order(symbol="tETHF0:USTF0", amount=0.01, leverage=5, limit_offset_percentage=0.002)
    # Or, override default by passing symbol directly:
    # my_trader.execute_order(symbol="tETHF0:USTF0", amount=0.01, leverage=5, limit_offset_percentage=0.002)

    # --- Demonstration: How to get wallets and positions (requires API keys) ---
    if bfx_wrapper.bfx_client:
        print("\n--- Account Information (if API keys are valid) ---")
        wallets = bfx_wrapper.get_wallets()
        if wallets:
            print("\nWallets:")
            for wallet in wallets:
                # Wallet object has attributes like type, currency, balance, etc.
                print(
                    f"  Type: {wallet.type}, Currency: {wallet.currency}, Balance: {wallet.balance}, Available: {wallet.balance_available}")
        else:
            print("\nCould not retrieve wallets.")

        positions = bfx_wrapper.get_positions()
        if positions:
            print("\nActive Positions:")
            if not positions:  # Check if the list is empty
                print("  No active positions.")
            else:
                for pos in positions:
                    # Position object has attributes like symbol, amount, base_price, etc.
                    print(
                        f"  Symbol: {pos.symbol}, Amount: {pos.amount}, Base Price: {pos.base_price}, P/L: {pos.pl}, P/L %: {pos.pl_perc}")
        else:
            print("\nCould not retrieve positions.")
    else:
        print("\nSkipping fetching wallets/positions as API client is not initialized.")