import os
import requests
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def search_serper_google_maps(query: str):
    """
    Get detailed Google Maps results via Serper API.
    Returns address, phone, website, rating, and reviews.
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY not found in environment")
        return None

    url = "https://google.serper.dev/maps"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Serper Maps error: {e}")
        return None

def search_serper_web(query: str):
    """
    Get web search results (including LinkedIn profiles and founder names).
    """
    if not SERPER_API_KEY:
        return None

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Serper Web error: {e}")
        return None
