import os
import json
import logging
import re
import asyncio
from src.config.models import get_agentrouter_model
from agents import Agent, Runner, ModelSettings
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template Registry — Maps niches to their template files
# ---------------------------------------------------------------------------
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")

TEMPLATE_REGISTRY = {
    "coffee": {
        "file": "coffee_app.html",
        "keywords": [
            "coffee", "café", "cafe", "roaster", "roastery", "espresso",
            "barista", "brew", "latte", "cappuccino", "tea house",
            "bakery", "pastry", "dessert", "donut", "bagel",
        ],
        "label": "Coffee / Café",
    },
    "salon": {
        "file": "salon_app.html",
        "keywords": [
            "salon", "hair", "barber", "barbershop", "beauty",
            "stylist", "hairdresser", "spa", "nails", "nail bar",
            "grooming", "blowout", "braids", "extensions", "lash",
            "waxing", "threading", "tanning", "aesthetics", "skincare",
            "medspa", "med spa", "cosmetic",
        ],
        "label": "Hair Salon / Beauty",
    },
    # Future niches — just add an entry here + a template file:
    # "fitness": { "file": "fitness_app.html", "keywords": [...], "label": "Gym / Fitness" },
    # "restaurant": { "file": "restaurant_app.html", "keywords": [...], "label": "Restaurant" },
    # "auto": { "file": "auto_app.html", "keywords": [...], "label": "Auto Shop" },
}

# Fallback if no niche matches
DEFAULT_NICHE = "coffee"


def detect_niche(business_type: str, business_name: str = "") -> str:
    """
    Intelligently detect which template niche to use based on
    business_type and business_name from the research data.
    Returns a key from TEMPLATE_REGISTRY.
    """
    search_text = f"{business_type} {business_name}".lower()

    # Score each niche by keyword matches
    best_niche = DEFAULT_NICHE
    best_score = 0

    for niche_key, niche_info in TEMPLATE_REGISTRY.items():
        score = 0
        for kw in niche_info["keywords"]:
            if kw in search_text:
                score += 1
                # Exact match in business_type is worth more
                if kw in business_type.lower():
                    score += 2
        if score > best_score:
            best_score = score
            best_niche = niche_key

    return best_niche


# ---------------------------------------------------------------------------
# SYSTEM PROMPTS — One per niche
# ---------------------------------------------------------------------------

COFFEE_CONFIG_PROMPT = """You are a senior mobile app UX designer. Your job is to generate a personalized APP_CONFIG JSON object for a coffee shop mobile app demo.

You will receive detailed business research data. Generate ONLY a valid JSON object — no markdown, no explanation, no code fences.

The JSON must follow this EXACT schema:

{
  "brandName": "Business Name Here",
  "brandTagline": "SPECIALTY COFFEE",
  "primaryColor": "#2D5A43",
  "primaryLight": "#3d7a5d",
  "primaryDark": "#1d3a2d",
  "accentColor": "#C8A96E",
  "founderName": "Founder Name",
  "founderRole": "Co-Founder",
  "storeName": "Downtown",
  "storeAddress": "Full address here",
  "storeHours": "6:00 AM – 8:00 PM",
  "googleRating": 4.7,
  "reviewCount": 2063,
  "currencySymbol": "$",
  "taxRate": 0.08,
  "categories": ["All", "Hot Beverages", "Cold Beverages", "Pastries"],
  "menuItems": [
    { "id": 1, "name": "Macchiato", "price": 4.50, "calories": 47, "category": "Hot Beverages", "popular": true, "icon": "fa-mug-hot", "gradient": ["#D4A574", "#8B6914"] },
    { "id": 2, "name": "Flat White", "price": 5.00, "calories": 71, "category": "Hot Beverages", "popular": false, "icon": "fa-mug-saucer", "gradient": ["#C4A882", "#6F4E37"] }
  ],
  "sizes": [
    { "name": "Small", "label": "S", "modifier": 0 },
    { "name": "Medium", "label": "M", "modifier": 0.75 },
    { "name": "Large", "label": "L", "modifier": 1.50 }
  ],
  "extras": [
    { "name": "Extra Shot", "price": 0.75, "icon": "fa-plus-circle" },
    { "name": "Almond Milk", "price": 0.50, "icon": "fa-seedling" },
    { "name": "Oat Milk", "price": 0.50, "icon": "fa-wheat-awn" },
    { "name": "No Sugar", "price": 0, "icon": "fa-ban" },
    { "name": "Iced", "price": 0, "icon": "fa-snowflake" }
  ],
  "loyaltyPoints": 2450,
  "loyaltyNextReward": "Free Coffee",
  "loyaltyProgress": 82,
  "loyaltyPerks": ["10 pts per $1 spent", "Free birthday drink", "Early access to new items"]
}

═══════════════════════════════════════════
RULES:
═══════════════════════════════════════════

1. brandName: Use the EXACT business name from the research data.
2. primaryColor: Choose a warm, brand-appropriate color:
   - Coffee roasters: deep green (#2D5A43), dark brown (#4A2C2A), or warm amber (#92400e)
   - Modern cafes: charcoal (#2D3436), navy (#1B2838), or deep teal (#1A535C)
   - Artisan shops: burgundy (#6B2737), forest (#2D5A43), or slate (#334155)
   Generate primaryLight (10% lighter) and primaryDark (15% darker) from primaryColor.
3. accentColor: Pick a complementary accent — gold (#C8A96E), warm orange (#E8985E), or copper (#B87333).
4. menuItems: Generate 6-8 realistic items based on the business type and what customers love:
   - Use realistic prices for the location
   - Include calories (estimate if not known)
   - Mark 3-4 items as "popular": true
   - Use appropriate FontAwesome icons: fa-mug-hot, fa-mug-saucer, fa-coffee, fa-glass-water, fa-bottle-water, fa-leaf, fa-bread-slice, fa-cookie, fa-ice-cream, fa-wine-glass
   - Use warm gradient colors for each item: coffee tones for hot drinks, cool tones for cold drinks, pastry tones for food
5. founderName: Extract the primary decision maker name. If multiple (e.g. "Jon and Andrea Allen"), use just the first name.
6. currencySymbol: Use the appropriate currency for the location ($ for US, £ for UK, SAR for Saudi, AED for UAE, etc.)
7. storeAddress: Use the actual address from research data.
8. googleRating & reviewCount: Use actual values from research.

OUTPUT: Return ONLY the raw JSON object. Start with { and end with }. No other text."""


SALON_CONFIG_PROMPT = """You are a senior mobile app UX designer. Your job is to generate a personalized APP_CONFIG JSON object for a hair salon / beauty studio mobile app demo.

You will receive detailed business research data. Generate ONLY a valid JSON object — no markdown, no explanation, no code fences.

The JSON must follow this EXACT schema:

{
  "brandName": "Business Name Here",
  "brandTagline": "PREMIUM HAIR CARE",
  "primaryColor": "#1a1a2e",
  "primaryLight": "#2d2d4a",
  "primaryDark": "#0f0f1a",
  "accentColor": "#e6a756",
  "founderName": "Founder Name",
  "founderRole": "Owner & Lead Stylist",
  "storeName": "Main Studio",
  "storeAddress": "Full address here",
  "storeHours": "9:00 AM – 7:00 PM",
  "googleRating": 4.8,
  "reviewCount": 1247,
  "currencySymbol": "$",
  "taxRate": 0.08,
  "categories": ["All", "Haircuts", "Color", "Treatments", "Styling"],
  "menuItems": [
    { "id": 1, "name": "Classic Haircut", "price": 45.00, "duration": "30 min", "category": "Haircuts", "popular": true, "icon": "fa-scissors", "gradient": ["#2d2d4a", "#1a1a2e"] },
    { "id": 2, "name": "Balayage Color", "price": 185.00, "duration": "2.5 hrs", "category": "Color", "popular": true, "icon": "fa-palette", "gradient": ["#e6a756", "#c4883a"] }
  ],
  "stylists": [
    { "name": "Sarah M.", "specialty": "Color Expert", "avatar": "#e6a756", "rating": 4.9 },
    { "name": "James K.", "specialty": "Barber", "avatar": "#3b82f6", "rating": 4.8 }
  ],
  "addOns": [
    { "name": "Scalp Massage", "price": 15, "icon": "fa-hand-sparkles" },
    { "name": "Hair Mask", "price": 20, "icon": "fa-jar" },
    { "name": "Toner Gloss", "price": 25, "icon": "fa-fill-drip" },
    { "name": "Trim Ends", "price": 10, "icon": "fa-scissors" },
    { "name": "Olaplex", "price": 35, "icon": "fa-flask" }
  ],
  "loyaltyPoints": 1850,
  "loyaltyNextReward": "Free Blowout",
  "loyaltyProgress": 74,
  "loyaltyPerks": ["5 pts per $1 spent", "Free birthday styling", "Early access to new services"]
}

═══════════════════════════════════════════
RULES:
═══════════════════════════════════════════

1. brandName: Use the EXACT business name from the research data.
2. primaryColor: Choose a luxurious, brand-appropriate color:
   - Upscale salons: deep navy (#1a1a2e), charcoal (#2D3436), or black (#111111)
   - Modern salons: deep plum (#3D1F4E), dark teal (#134E5E), or slate (#1E293B)
   - Trendy/boho: dusty rose (#6B3A4A), sage (#4A5D4A), or warm brown (#4A2C2A)
   Generate primaryLight (10% lighter) and primaryDark (15% darker) from primaryColor.
3. accentColor: Pick a luxe accent — gold (#e6a756), rose gold (#B76E79), or champagne (#D4AF37).
4. menuItems: Generate 6-8 realistic salon services based on the business:
   - Use realistic prices for the location and salon tier
   - Include duration (e.g. "30 min", "1.5 hrs", "2 hrs")
   - Mark 3-4 items as "popular": true
   - Use appropriate FontAwesome icons: fa-scissors, fa-palette, fa-wind, fa-wand-magic-sparkles, fa-fill-drip, fa-droplet, fa-crown, fa-spray-can-sparkles, fa-hand-sparkles
   - Use elegant gradient colors for each service
5. stylists: Generate 3-4 stylists with names, specialties, avatar colors, and ratings.
6. addOns: Generate 4-5 add-on services with prices and icons.
7. founderName: Extract the primary decision maker name.
8. currencySymbol: Use the appropriate currency for the location.
9. storeAddress: Use the actual address from research data.
10. googleRating & reviewCount: Use actual values from research.

OUTPUT: Return ONLY the raw JSON object. Start with { and end with }. No other text."""


NICHE_PROMPTS = {
    "coffee": COFFEE_CONFIG_PROMPT,
    "salon": SALON_CONFIG_PROMPT,
}


def _extract_json(text: str) -> dict:
    """Extract and parse JSON from the agent's response."""
    text = (text or "").strip()
    
    # Remove markdown fences if present
    match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    
    # Find the JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    
    return json.loads(text)


def _build_config_request(business_name: str, research_data: dict, niche: str) -> str:
    """Build a concise request for the config generation agent."""
    
    founder = research_data.get("decision_maker_name", "Manager")
    if founder in ("Not Found", "Unknown", "", None):
        founder = "Manager"
    
    niche_label = TEMPLATE_REGISTRY.get(niche, {}).get("label", niche)
    
    return f"""Generate the APP_CONFIG JSON for this {niche_label} business:

BUSINESS: {business_name}
TYPE: {research_data.get("business_type", "Not specified")}
LOCATION: {research_data.get("location", "Not Found")}
RATING: {research_data.get("google_rating", "")}
FOUNDER: {founder}
WEBSITE: {research_data.get("website", "")}

WHAT CUSTOMERS LOVE:
{research_data.get("what_customers_love", "Great service")}

PAIN POINTS:
1. {research_data.get("top_pain_theme_1", "")}
2. {research_data.get("top_pain_theme_2", "")}
3. {research_data.get("top_pain_theme_3", "")}

REVIEWS MENTIONING PRODUCTS:
{chr(10).join('- "' + r + '"' for r in research_data.get("reviews", [])[:3] if r)}

Generate the JSON now. Start with {{ and end with }}."""


def _inject_config_into_template(template_html: str, config: dict) -> str:
    """Replace the APP_CONFIG block in the template with the personalized config."""
    config_js = "const APP_CONFIG = " + json.dumps(config, indent=4, ensure_ascii=False) + ";"
    
    # Find and replace the config block between the markers
    pattern = r"const APP_CONFIG = \{.*?\};"
    replacement = config_js
    
    result = re.sub(pattern, replacement, template_html, count=1, flags=re.DOTALL)
    return result


def _get_default_config(business_name: str, research_data: dict, niche: str) -> dict:
    """Generate a reasonable default config without calling the LLM (fallback)."""
    founder = research_data.get("decision_maker_name", "Manager")
    if founder in ("Not Found", "Unknown", "", None):
        founder = "Manager"
    # Clean founder name: take first name if "Jon Allen (Co-Founder)"
    founder = re.sub(r'\s*\(.*?\)', '', founder).split(' and ')[0].strip()
    
    location = research_data.get("location", "")
    rating_str = research_data.get("google_rating", "4.5")
    try:
        rating = float(re.search(r'[\d.]+', str(rating_str)).group())
    except:
        rating = 4.5
    review_str = str(rating_str)
    try:
        review_count = int(re.search(r'\((\d+)', review_str).group(1))
    except:
        review_count = 500

    if niche == "salon":
        return _get_default_salon_config(business_name, founder, location, rating, review_count)
    else:
        return _get_default_coffee_config(business_name, founder, location, rating, review_count)


def _get_default_coffee_config(name, founder, location, rating, review_count):
    return {
        "brandName": name,
        "brandTagline": "SPECIALTY COFFEE",
        "primaryColor": "#2D5A43",
        "primaryLight": "#3d7a5d",
        "primaryDark": "#1d3a2d",
        "accentColor": "#C8A96E",
        "founderName": founder,
        "founderRole": "Founder",
        "storeName": "Main",
        "storeAddress": location or "Visit us today",
        "storeHours": "6:00 AM – 8:00 PM",
        "googleRating": rating,
        "reviewCount": review_count,
        "currencySymbol": "$",
        "taxRate": 0.08,
        "categories": ["All", "Hot Beverages", "Cold Beverages", "Pastries"],
        "menuItems": [
            {"id":1,"name":"Macchiato","price":4.50,"calories":47,"category":"Hot Beverages","popular":True,"icon":"fa-mug-hot","gradient":["#D4A574","#8B6914"]},
            {"id":2,"name":"Flat White","price":5.00,"calories":71,"category":"Hot Beverages","popular":False,"icon":"fa-mug-saucer","gradient":["#C4A882","#6F4E37"]},
            {"id":3,"name":"Cappuccino","price":4.75,"calories":79,"category":"Hot Beverages","popular":True,"icon":"fa-coffee","gradient":["#C9956B","#7B4B2A"]},
            {"id":4,"name":"Americano","price":3.50,"calories":5,"category":"Hot Beverages","popular":False,"icon":"fa-mug-hot","gradient":["#8B7355","#4A3728"]},
            {"id":5,"name":"Iced Latte","price":5.50,"calories":150,"category":"Cold Beverages","popular":True,"icon":"fa-glass-water","gradient":["#87CEEB","#4682B4"]},
            {"id":6,"name":"Cold Brew","price":4.50,"calories":10,"category":"Cold Beverages","popular":False,"icon":"fa-bottle-water","gradient":["#6B8E9B","#3D5A6B"]},
            {"id":7,"name":"Chai Latte","price":5.25,"calories":120,"category":"Hot Beverages","popular":True,"icon":"fa-leaf","gradient":["#A8C686","#5D7B3A"]},
            {"id":8,"name":"Croissant","price":3.75,"calories":230,"category":"Pastries","popular":False,"icon":"fa-bread-slice","gradient":["#DEB887","#B8860B"]},
        ],
        "sizes": [
            {"name":"Small","label":"S","modifier":0},
            {"name":"Medium","label":"M","modifier":0.75},
            {"name":"Large","label":"L","modifier":1.50},
        ],
        "extras": [
            {"name":"Extra Shot","price":0.75,"icon":"fa-plus-circle"},
            {"name":"Almond Milk","price":0.50,"icon":"fa-seedling"},
            {"name":"Oat Milk","price":0.50,"icon":"fa-wheat-awn"},
            {"name":"No Sugar","price":0,"icon":"fa-ban"},
            {"name":"Iced","price":0,"icon":"fa-snowflake"},
        ],
        "loyaltyPoints": 2450,
        "loyaltyNextReward": "Free Coffee",
        "loyaltyProgress": 82,
        "loyaltyPerks": ["10 pts per $1 spent", "Free birthday drink", "Early access to new items"],
    }


def _get_default_salon_config(name, founder, location, rating, review_count):
    return {
        "brandName": name,
        "brandTagline": "PREMIUM HAIR CARE",
        "primaryColor": "#1a1a2e",
        "primaryLight": "#2d2d4a",
        "primaryDark": "#0f0f1a",
        "accentColor": "#e6a756",
        "founderName": founder,
        "founderRole": "Owner & Stylist",
        "storeName": "Main Studio",
        "storeAddress": location or "Visit us today",
        "storeHours": "9:00 AM – 7:00 PM",
        "googleRating": rating,
        "reviewCount": review_count,
        "currencySymbol": "$",
        "taxRate": 0.08,
        "categories": ["All", "Haircuts", "Color", "Treatments", "Styling"],
        "menuItems": [
            {"id":1,"name":"Classic Haircut","price":45.00,"duration":"30 min","category":"Haircuts","popular":True,"icon":"fa-scissors","gradient":["#2d2d4a","#1a1a2e"]},
            {"id":2,"name":"Balayage Color","price":185.00,"duration":"2.5 hrs","category":"Color","popular":True,"icon":"fa-palette","gradient":["#e6a756","#c4883a"]},
            {"id":3,"name":"Blowout & Style","price":55.00,"duration":"45 min","category":"Styling","popular":True,"icon":"fa-wind","gradient":["#8b5cf6","#6d28d9"]},
            {"id":4,"name":"Keratin Treatment","price":250.00,"duration":"3 hrs","category":"Treatments","popular":True,"icon":"fa-wand-magic-sparkles","gradient":["#ec4899","#be185d"]},
            {"id":5,"name":"Men's Fade","price":35.00,"duration":"25 min","category":"Haircuts","popular":False,"icon":"fa-scissors","gradient":["#3b82f6","#1d4ed8"]},
            {"id":6,"name":"Root Touch-Up","price":85.00,"duration":"1.5 hrs","category":"Color","popular":False,"icon":"fa-fill-drip","gradient":["#f59e0b","#d97706"]},
            {"id":7,"name":"Deep Conditioning","price":40.00,"duration":"30 min","category":"Treatments","popular":False,"icon":"fa-droplet","gradient":["#10b981","#059669"]},
            {"id":8,"name":"Updo / Event","price":95.00,"duration":"1 hr","category":"Styling","popular":False,"icon":"fa-crown","gradient":["#f43f5e","#e11d48"]},
        ],
        "stylists": [
            {"name":"Sarah M.","specialty":"Color Expert","avatar":"#e6a756","rating":4.9},
            {"name":"James K.","specialty":"Barber","avatar":"#3b82f6","rating":4.8},
            {"name":"Maria L.","specialty":"Stylist","avatar":"#ec4899","rating":4.7},
            {"name":"Alex R.","specialty":"Extensions","avatar":"#8b5cf6","rating":4.9},
        ],
        "addOns": [
            {"name":"Scalp Massage","price":15,"icon":"fa-hand-sparkles"},
            {"name":"Hair Mask","price":20,"icon":"fa-jar"},
            {"name":"Toner Gloss","price":25,"icon":"fa-fill-drip"},
            {"name":"Trim Ends","price":10,"icon":"fa-scissors"},
            {"name":"Olaplex","price":35,"icon":"fa-flask"},
        ],
        "loyaltyPoints": 1850,
        "loyaltyNextReward": "Free Blowout",
        "loyaltyProgress": 74,
        "loyaltyPerks": ["5 pts per $1 spent", "Free birthday styling", "Early access to new services"],
    }


async def build_demo_for_lead(business_name: str, research_data: dict) -> str:
    """
    Multi-niche Template + Config pattern.
    1. Detect the business niche (coffee, salon, etc.)
    2. Pick the right template
    3. Agent generates a small APP_CONFIG JSON (~50 lines)
    4. Config is injected into the chosen template
    5. Result is saved as the demo file
    
    This is 10x faster, 10x cheaper, and produces consistent premium quality.
    """
    os.makedirs("demos", exist_ok=True)
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', business_name).lower()
    file_path = f"demos/{safe_name}_demo.html"
    
    # Skip if already exists
    if os.path.exists(file_path):
        logger.info(f"Demo already exists for {business_name}")
        return file_path
    
    # STEP 1: Detect niche
    business_type = research_data.get("business_type", "")
    niche = detect_niche(business_type, business_name)
    niche_info = TEMPLATE_REGISTRY[niche]
    template_path = os.path.join(TEMPLATE_DIR, niche_info["file"])
    
    print(f"  [DEMO] 🎯 Detected niche: {niche_info['label']} (template: {niche_info['file']})")
    
    # Load the template
    if not os.path.exists(template_path):
        logger.error(f"Template not found: {template_path}")
        return "Failed — template file not found"
    
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()
    
    logger.info(f"Building demo for: {business_name} (niche={niche})")
    print(f"  [DEMO] Generating config for {business_name}...")
    
    config = None
    max_attempts = 2
    
    for attempt in range(1, max_attempts + 1):
        try:
            model = get_agentrouter_model()
            
            # Pick the right system prompt for this niche
            system_prompt = NICHE_PROMPTS.get(niche, COFFEE_CONFIG_PROMPT)
            
            agent = Agent(
                name="Demo Config Agent",
                instructions=system_prompt,
                model=model,
                model_settings=ModelSettings(temperature=0.5),
            )
            
            user_message = _build_config_request(business_name, research_data, niche)
            result = await Runner.run(agent, input=user_message)
            raw_output = result.final_output
            
            config = _extract_json(raw_output)
            
            # Validate essential fields
            if config.get("brandName") and config.get("menuItems"):
                print(f"  [DEMO] Config generated: {len(config.get('menuItems', []))} services")
                break
            else:
                print(f"  [DEMO] [WARN] Config missing fields, attempt {attempt}")
                config = None
                
        except Exception as e:
            logger.error(f"Config generation error (attempt {attempt}): {e}")
            print(f"  [DEMO] [ERROR] Attempt {attempt}: {e}")
            if attempt < max_attempts:
                await asyncio.sleep(2)
    
    # Fallback to default config if LLM failed
    if not config:
        print(f"  [DEMO] Using default config (LLM failed)")
        config = _get_default_config(business_name, research_data, niche)
    
    # Inject config into template
    final_html = _inject_config_into_template(template_html, config)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_html)
    
    print(f"  [DEMO] [SUCCESS] Saved: {file_path} ({len(final_html)} chars) [{niche_info['label']}]")
    return file_path
