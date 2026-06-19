import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(account_sid, auth_token)

numbers_to_test = ["+917207111592", "+919014728365"]

for number in numbers_to_test:
    print(f"\nTrying to send to {number}...")
    try:
        message = client.messages.create(
            body="WillGuard Direct Test Message",
            from_=from_number,
            to=number
        )
        print(f"✅ SUCCESS! Sent to {number}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ FAILED to send to {number}.")
        print(f"Error: {e}")
