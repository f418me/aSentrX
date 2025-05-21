import os
from bfxapi import Client, REST_HOST
from bfxapi.types import Notification, Order
from dotenv import load_dotenv

load_dotenv()

bfx = Client(
    rest_host=REST_HOST,
    api_key=os.getenv("BFX_API_KEY"),
    api_secret=os.getenv("BFX_API_SECRET")
)

print(bfx.rest.auth.get_wallets())
print(bfx.rest.auth.get_positions())




