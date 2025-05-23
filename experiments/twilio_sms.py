import os

from twilio.rest import Client

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']

client = Client(account_sid, auth_token)
message = client.messages.create(from_='+13204336759', body='Wir haben gekauft', to='+41796754690')
print(message.sid)