import asyncio
import json
import logging
import os
from src.tools.serper_tool import search_serper_google_maps, search_serper_web
from src.tools.google_places_tool import get_google_place_details
from src.tools.searchapi_tool import search_searchapi
from src.tools.tavily_tool import search_tavily
from src.tools.exa_tool import search_exa
from src.tools.search_tools import search_duckduckgo
from agents import function_tool

logger = logging.getLogger(__name__)

async def _smart_web_search_logic(query: str):
    """
    Tries multiple search tools to save credits.
    DDG -> SearchAPI -> Serper
    """
    # 1. Try DuckDuckGo (Free)
    try:
        results = search_duckduckgo(query)
        if results and len(results) > 0:
            return {"organic": results}
    except: pass

    # 2. Try SearchAPI (Free credits)
    if os.getenv("SEARCHAPI_API_KEY"):
        res = search_searchapi(query)
        if res: return res

    # 3. Try Tavily
    if os.getenv("TAVILY_API_KEY"):
        res = search_tavily(query)
        if res: return res

    # 4. Try Exa
    if os.getenv("EXA_API_KEY"):
        res = search_exa(query)
        if res: return res

    # 5. Try Serper (Premium/Fallback)
    if os.getenv("SERPER_API_KEY"):
        res = search_serper_web(query)
        if res: return res
    
    return None

@function_tool(strict_mode=False)
async def smart_web_search(query: str):
    return await _smart_web_search_logic(query)

@function_tool(strict_mode=False)
async def scrape_google_maps_reviews(
    business_name: str,
    max_reviews: int = 15,
    maps_url: str | None = None,
    location_hint: str | None = None,
):
    """
    OFFICIAL GOOGLE PLACES API + SMART SEARCH.
    """
    logger.info(f"Smart Researching: {business_name}")
    
    # 1. Official Google Places API (Reviews)
    place = get_google_place_details(business_name, location_hint or "")
    
    details = {
        "name": business_name, "reviews": [], "rating": "N/A", "address": "N/A",
        "website": "N/A", "phone": "N/A", "peak_hours": "Not Found",
        "maps_review_count_text": "Not Found", "maps_about_text": "Not Found",
    }

    if place:
        details["name"] = place.get("name", business_name)
        details["rating"] = place.get("rating", "N/A")
        details["address"] = place.get("formatted_address", "N/A")
        details["website"] = place.get("website", "N/A")
        details["phone"] = place.get("formatted_phone_number", "N/A")
        
        if "reviews" in place:
            for r in place["reviews"]:
                details["reviews"].append({
                    "text": r.get("text", ""),
                    "author": r.get("author_name", "Anonymous"),
                    "rating": r.get("rating", 0),
                    "source": "Official Google Review"
                })

    details["reviews_scraped"] = len(details["reviews"])
    return details

@function_tool(strict_mode=False)
async def find_founder_info(business_name: str) -> dict:
    """Multi-query Smart Founder Hunt."""
    query = f'"{business_name}" founder owner LinkedIn'
    data = await _smart_web_search_logic(query)
    
    info = {"name": "Not Found", "linkedin": "Not Found"}
    if data and "organic" in data:
        for res in data["organic"]:
            link = res.get("link", "")
            if "linkedin.com/in/" in link:
                info["linkedin"] = link
                title = res.get("title", "").split("-")[0].split("|")[0].strip()
                if len(title.split()) <= 3:
                    info["name"] = title
                    return info
    return info

if __name__ == "__main__":
    import sys
    asyncio.run(scrape_google_maps_reviews(sys.argv[1] if len(sys.argv)>1 else "Seven Fortunes Coffee Roasters"))
