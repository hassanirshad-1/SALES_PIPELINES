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


def _normalize_results(raw_results: list[dict]) -> list[dict]:
    """Normalize search results to consistent keys: title, link, snippet."""
    normalized = []
    for r in (raw_results or []):
        normalized.append({
            "title": r.get("title", ""),
            "link": r.get("link") or r.get("href") or r.get("url", ""),
            "snippet": r.get("snippet") or r.get("body") or r.get("content") or r.get("text", ""),
        })
    return normalized


async def _smart_web_search_logic(query: str):
    """
    Tries multiple search tools to save credits.
    DDG -> SearchAPI -> Tavily -> Exa -> Serper
    
    Returns normalized results with consistent keys: title, link, snippet.
    """
    # 1. Try DuckDuckGo (Free) — run in thread since it's sync
    try:
        results = await asyncio.to_thread(search_duckduckgo, query)
        if results and len(results) > 0:
            return {"organic": _normalize_results(results)}
    except Exception:
        pass

    # 2. Try SearchAPI (Free credits)
    if os.getenv("SEARCHAPI_API_KEY"):
        try:
            res = search_searchapi(query)
            if res and res.get("organic"):
                return {"organic": _normalize_results(res["organic"])}
        except Exception:
            pass

    # 3. Try Tavily
    if os.getenv("TAVILY_API_KEY"):
        try:
            res = search_tavily(query)
            if res and res.get("organic"):
                return {"organic": _normalize_results(res["organic"])}
        except Exception:
            pass

    # 4. Try Exa
    if os.getenv("EXA_API_KEY"):
        try:
            res = search_exa(query)
            if res and res.get("organic"):
                return {"organic": _normalize_results(res["organic"])}
        except Exception:
            pass

    # 5. Try Serper (Premium/Fallback)
    if os.getenv("SERPER_API_KEY"):
        try:
            res = search_serper_web(query)
            if res:
                # Serper returns different format
                organic = res.get("organic", [])
                if organic:
                    return {"organic": _normalize_results(organic)}
        except Exception:
            pass
    
    return {"organic": [], "note": "All search providers returned no results"}


@function_tool(strict_mode=False)
async def batch_web_search(queries: list[str]) -> dict:
    """
    ⚡ BATCH SEARCH — Run MULTIPLE search queries in parallel in a single tool call.
    Much more efficient than calling smart_web_search multiple times.
    
    Example: batch_web_search(queries=["Business Instagram", "Business app", "Business founder"])
    Returns: {"results": {"query1": {...}, "query2": {...}, ...}}
    """
    results = {}
    # Run all queries concurrently
    tasks = [_smart_web_search_logic(q) for q in queries[:6]]  # Cap at 6 to be safe
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    for query, response in zip(queries[:6], responses):
        if isinstance(response, Exception):
            results[query] = {"organic": [], "error": str(response)}
        else:
            results[query] = response or {"organic": []}
    
    return {"results": results}


@function_tool(strict_mode=False)
async def smart_web_search(query: str) -> dict:
    """
    Search the web using multiple providers (cheapest first).
    Use this for ANY general query: social media profiles, delivery platforms,
    competitor research, business age, mobile apps, etc.
    Returns: {"organic": [{"title": "...", "link": "...", "snippet": "..."}]}
    """
    return await _smart_web_search_logic(query)


@function_tool(strict_mode=False)
async def scrape_google_maps_reviews(
    business_name: str,
    max_reviews: int = 15,
    maps_url: str | None = None,
    location_hint: str | None = None,
) -> dict:
    """
    Get official business data from Google Places API.
    Returns: name, rating, review_count, address, website, phone, 
    opening_hours, and up to 5 real verbatim Google reviews.
    ALWAYS call this first for any business research.
    """
    logger.info(f"Smart Researching: {business_name}")
    
    # 1. Official Google Places API (Reviews)
    place = get_google_place_details(business_name, location_hint or "")
    
    details = {
        "name": business_name, "reviews": [], "rating": "N/A", "address": "N/A",
        "website": "N/A", "phone": "N/A", "peak_hours": "Not Found",
        "review_count": 0, "opening_hours": "Not Found",
    }

    if place:
        details["name"] = place.get("name", business_name)
        details["rating"] = place.get("rating", "N/A")
        details["address"] = place.get("formatted_address", "N/A")
        details["website"] = place.get("website", "N/A")
        details["phone"] = place.get("formatted_phone_number", "N/A")
        
        # Extract opening hours
        hours = place.get("opening_hours", {})
        if hours and hours.get("weekday_text"):
            details["opening_hours"] = "; ".join(hours["weekday_text"])
        
        # Extract review count (user_ratings_total)
        details["review_count"] = place.get("user_ratings_total", len(place.get("reviews", [])))
        
        if "reviews" in place:
            for r in place["reviews"]:
                details["reviews"].append({
                    "text": r.get("text", ""),
                    "author": r.get("author_name", "Anonymous"),
                    "rating": r.get("rating", 0),
                    "language": r.get("language", "en"),
                    "relative_time": r.get("relative_time_description", ""),
                    "source": "Official Google Review"
                })

    details["reviews_scraped"] = len(details["reviews"])
    
    # Format rating string for easy consumption
    if details["rating"] != "N/A":
        details["formatted_rating"] = f"{details['rating']} ⭐ ({details['review_count']} reviews)"
    else:
        details["formatted_rating"] = "Not Found"
    
    return details


@function_tool(strict_mode=False)
async def find_founder_info(business_name: str, location_hint: str | None = None) -> dict:
    """
    Multi-query hunt for business owner/founder name and LinkedIn profile.
    Tries multiple search patterns to maximize hit rate.
    Returns: {"name": "...", "linkedin": "...", "email": "...", "role": "..."}
    """
    info = {"name": "Not Found", "linkedin": "Not Found", "email": "Not Found", "role": "Not Found"}
    
    # Multiple query patterns — try each until we find something
    loc = location_hint or ""
    queries = [
        f'"{business_name}" founder owner LinkedIn',
        f'"{business_name}" {loc} CEO founder "coffee" site:linkedin.com',
        f'"{business_name}" "about us" founder owner established',
        f'"{business_name}" owner manager crunchbase',
    ]
    
    for query in queries:
        data = await _smart_web_search_logic(query)
        if not data or "organic" not in data:
            continue
            
        for res in data["organic"]:
            link = res.get("link", "")
            title = res.get("title", "")
            snippet = res.get("snippet", "")
            
            # Found LinkedIn profile
            if "linkedin.com/in/" in link:
                info["linkedin"] = link
                # Extract name from LinkedIn title format: "Name - Title - Company"
                name_part = title.split("-")[0].split("|")[0].split("–")[0].strip()
                if 1 <= len(name_part.split()) <= 4:
                    info["name"] = name_part
                    # Try to extract role from title
                    if "-" in title:
                        role_part = title.split("-")[1].strip() if len(title.split("-")) > 1 else ""
                        if role_part and len(role_part) < 50:
                            info["role"] = role_part
                    return info  # Found on LinkedIn — good enough
            
            # Check snippets for founder/owner names
            combined = f"{title} {snippet}".lower()
            if any(word in combined for word in ["founder", "owner", "ceo", "co-founder"]):
                # Try to extract name — look for patterns like "Founded by Name" or "Owner: Name"
                import re
                patterns = [
                    r'(?:founded|owned|started|created)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
                    r'(?:founder|owner|ceo)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
                ]
                for pattern in patterns:
                    match = re.search(pattern, f"{title} {snippet}", re.IGNORECASE)
                    if match:
                        candidate = match.group(1).strip()
                        if 2 <= len(candidate) <= 40 and info["name"] == "Not Found":
                            info["name"] = candidate
        
        # If we found a name from non-LinkedIn source, stop searching
        if info["name"] != "Not Found":
            break
    
    return info


if __name__ == "__main__":
    import sys
    asyncio.run(scrape_google_maps_reviews(sys.argv[1] if len(sys.argv)>1 else "Seven Fortunes Coffee Roasters"))
