import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def search_tavily(query: str, num_results: int = 5):
    """
    Search via Tavily API.
    """
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not found.")
        return None

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "max_results": num_results
    }
    
    try:
        res = requests.post(url, json=payload).json()
        if "results" in res:
            return {"organic": [{"title": i.get("title"), "link": i.get("url"), "snippet": i.get("content")} for i in res["results"]]}
    except Exception as e:
        logger.error(f"Tavily Error: {e}")
    return None
