import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

def get_google_place_details(business_name: str, location_hint: str = ""):
    """
    Fetch official details and REVIEWS from Google Places API.
    Returns: name, rating, user_ratings_total, formatted_address, website,
    formatted_phone_number, reviews, opening_hours, types, business_status.
    """
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_PLACES_API_KEY not found")
        return None

    # 1. Find the Place ID
    search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": f"{business_name} {location_hint}",
        "inputtype": "textquery",
        "fields": "place_id,name,formatted_address",
        "key": GOOGLE_API_KEY
    }
    
    try:
        search_res = requests.get(search_url, params=params).json()
        if not search_res.get("candidates"):
            logger.warning(f"No Google Places candidates for: {business_name} {location_hint}")
            return None
        
        place_id = search_res["candidates"][0]["place_id"]
        
        # 2. Get Details — request ALL useful fields
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": ",".join([
                "name",
                "rating",
                "user_ratings_total",
                "formatted_phone_number",
                "international_phone_number",
                "website",
                "reviews",
                "opening_hours",
                "formatted_address",
                "types",
                "business_status",
                "price_level",
                "url",  # Google Maps URL
            ]),
            "key": GOOGLE_API_KEY,
            "reviews_sort": "newest",  # Get most recent reviews
        }
        
        details_res = requests.get(details_url, params=details_params).json()
        result = details_res.get("result")
        
        if result:
            logger.info(f"Google Places found: {result.get('name')} | Rating: {result.get('rating')} | Reviews: {result.get('user_ratings_total', 0)}")
        
        return result
    except Exception as e:
        logger.error(f"Google Places Error: {e}")
        return None
