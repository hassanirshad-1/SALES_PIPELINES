import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

EXA_API_KEY = os.getenv("EXA_API_KEY")

def search_exa(query: str, num_results: int = 5):
    """
    Search via Exa (Metaphor) API.
    """
    if not EXA_API_KEY:
        logger.warning("EXA_API_KEY not found.")
        return None

    url = "https://api.exa.ai/search"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": EXA_API_KEY
    }
    payload = {
        "query": query,
        "numResults": num_results
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if "results" in res:
            return {"organic": [{"title": i.get("title"), "link": i.get("url"), "snippet": i.get("text", "")} for i in res["results"]]}
    except Exception as e:
        logger.error(f"Exa Error: {e}")
    return None
