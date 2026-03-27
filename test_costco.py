import tls_client
import sys

session = tls_client.Session(client_identifier="chrome112", random_tls_extension_order=True)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.costco.com/',
    'Connection': 'keep-alive'
}
response = session.get("https://www.costco.com/AjaxGetContractPrice?itemId=100142101&productId=100142101", headers=headers)
print("STATUS:", response.status_code)
print("BODY:", response.text[:200])
