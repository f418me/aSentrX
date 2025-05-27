from exchanges.bitfinex_trader import BitfinexTrader
from trader.trader import Trader

if __name__ == '__main__':


    # Initialize BitfinexTrader (it will load keys from .env by default)
    # You can also set default symbol or order params here if needed
    bfx_wrapper = BitfinexTrader(default_symbol="tBTCF0:USTF0")

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