import os
import resend
from dotenv import load_dotenv

load_dotenv()
resend.api_key = os.environ.get("RESEND_API_KEY")
try:
    response = resend.Emails.send({
        "from": "Costco Agent <onboarding@resend.dev>",
        "to": ["sravya.iitkgp@gmail.com"],
        "subject": "Resend API Test",
        "html": "<html><body>Hello testing resend error handling</body></html>"
    })
    print("SUCCESS")
    print(response)
except Exception as e:
    print("EXCEPTION CAUGHT")
    print(e)
