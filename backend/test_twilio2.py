import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_PHONE_NUMBER")

try:
    client = Client(account_sid, auth_token)
    numbers_to_test = ["+917207111592", "+919014728365"]
    
    with open('twilio_test_results.txt', 'w', encoding='utf-8') as f:
        for number in numbers_to_test:
            f.write(f"Trying to send to {number}...\n")
            try:
                message = client.messages.create(
                    body="WillGuard Direct Test Message",
                    from_=from_number,
                    to=number
                )
                f.write(f"PASS: Sent to {number}. SID: {message.sid}\n\n")
            except Exception as e:
                f.write(f"FAIL: Failed to send to {number}.\n")
                f.write(f"Error: {e}\n\n")
except Exception as e:
    with open('twilio_test_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"Init Error: {e}")
