import os
import requests
from dotenv import load_dotenv

load_dotenv()

service_id = os.getenv("EMAILJS_SERVICE_ID")
template_id = os.getenv("EMAILJS_TEMPLATE_ID")
public_key = os.getenv("EMAILJS_PUBLIC_KEY")
private_key = os.getenv("EMAILJS_PRIVATE_KEY")

payload = {
    "service_id": service_id,
    "template_id": template_id,
    "user_id": public_key,
    "accessToken": private_key,
    "template_params": {
        "to_email": "test@example.com",
        "message": "Testing EmailJS direct from Python",
    }
}

try:
    url = "https://api.emailjs.com/api/v1.0/email/send"
    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
    
    with open('emailjs_test_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"Status Code: {response.status_code}\n")
        f.write(f"Response Body: {response.text}\n")
        
except Exception as e:
    with open('emailjs_test_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"Request Error: {str(e)}\n")
