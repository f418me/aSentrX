import os
from bfxapi import Client, REST_HOST
from dotenv import load_dotenv
import requests
load_dotenv()

bfx = Client(
    rest_host=REST_HOST,
    api_key=os.getenv("BFX_API_KEY"),
    api_secret=os.getenv("BFX_API_SECRET")
)

#print(bfx.rest.auth.get_wallets())
#print(bfx.rest.auth.get_positions())

# Attention executes order
#print(bfx.rest.auth.submit_order(type="LIMIT", symbol="tBTCF0:USTF0", amount="0.01", price="111600", lev=10))


# not working
#print(bfx.rest.public.get_derivatives_status("tBTCF0:USTF0,tETHF0:USTF0"))



url = "https://api-pub.bitfinex.com/v2/status/deriv?keys=tBTCF0:USTF0"

headers = {"accept": "application/json"}

response = requests.get(url, headers=headers)

print(response.text)


url = "https://api-pub.bitfinex.com/v2/book/tBTCF0:USTF0/P0?len=25"

headers = {"accept": "application/json"}

response = requests.get(url, headers=headers)

print(response.text)