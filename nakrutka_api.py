import requests
from config import NAKRUTKA_API_KEY

def place_order(service_id, link, quantity):
    url = 'https://nakrutka.cc/api/v2'
    payload = {
        'key': NAKRUTKA_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    response = requests.post(url, data=payload)
    return response.json()
