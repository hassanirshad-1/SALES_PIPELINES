import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SEARCHAPI_KEY = os.getenv("SEARCHAPI_API_KEY")

def search_searchapi(query: str, num_results: int = 5):
    """
    Search via SearchAPI.io (1,000 free searches usually).
    """
    if not SEARCHAPI_KEY:
        logger.warning("SEARCHAPI_API_KEY not found.")
        return None

    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SEARCHAPI_KEY,
        "num": num_results
    }
    
    try:
        res = requests.get(url, params=params).json()
        if "organic_results" in res:
            return {"organic": [{"title": i.get("title"), "link": i.get("link"), "snippet": i.get("snippet")} for i in res["organic_results"]]}
    except Exception as e:
        logger.error(f"SearchAPI Error: {e}")
    return None
