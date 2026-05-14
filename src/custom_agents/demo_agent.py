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
# SYSTEM PROMPT — defines the agent's role and design standards.
# The actual business data is injected into the user message via _build_demo_request().
# ---------------------------------------------------------------------------
DEMO_SYSTEM_PROMPT = """You are an elite UI/UX designer and Senior Frontend Engineer who builds stunning, hyper-personalized mobile app prototypes.

You will receive detailed business research data. Your job is to create a COMPLETE, HIGH-FIDELITY, production-quality iOS mobile app mockup as a single HTML file.

═══════════════════════════════════════════════════════════
ABSOLUTE NON-NEGOTIABLES:
═══════════════════════════════════════════════════════════

1. OUTPUT FORMAT: Return ONLY raw HTML code. Start IMMEDIATELY with <!DOCTYPE html>. No markdown. No explanation. No ```html fences.

2. iOS NATIVE LOOK: The design MUST look exactly like a real iOS app, NOT a website:
   - Centered mobile container: max-width 430px, min-height 100vh, relative overflow-hidden
   - iOS status bar at top (9:41, signal/wifi/battery icons)
   - Fixed bottom navigation bar with 4 tabs (Home, Order, Rewards, Profile) using FontAwesome icons
   - Apple-style design language: rounded-3xl corners, large bold SF-style typography, subtle shadows

3. TAILWIND CSS via CDN: <script src="https://cdn.tailwindcss.com"></script>
4. FONTAWESOME CDN: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
5. GOOGLE FONTS: Import Inter font for premium typography.

═══════════════════════════════════════════════════════════
DESIGN LANGUAGE — Apple-Inspired Premium:
═══════════════════════════════════════════════════════════

- Background: bg-gray-50 (light gray, NOT pure white)
- Cards: bg-white rounded-2xl or rounded-3xl with shadow-sm and border border-gray-100
- Primary accent: Choose a warm, brand-appropriate color (amber for coffee, emerald for health, etc.)
- Typography: font-sans, tracking-tight, font-bold for headings, text-gray-900 for primary text
- Spacing: Generous padding (p-5, px-6), breathing room between sections
- Gradients: Use gradient hero cards (from-{color}-700 to-{color}-900) for key CTAs
- Icons: Use FontAwesome icons in rounded containers (w-12 h-12 bg-{color}-100 rounded-xl)

═══════════════════════════════════════════════════════════
REQUIRED APP SCREENS (implement ALL with tab navigation):
═══════════════════════════════════════════════════════════

SCREEN 1 — HOME:
- Personalized welcome: "Welcome back, {founder_name}" with admin badge
- Hero CTA card with gradient solving their #1 pain point (e.g., "Skip the Line — Order Ahead")
- "Recommended for You" section featuring items customers actually love
- Customer Favorites horizontal scroll (3-4 items with icons, names, ratings)
- Social proof card showing a real review quote (styled as "Issue Detected & Fixed")
- Staff/operational tool card if relevant

SCREEN 2 — ORDER:
- "Order Ahead" header with pickup time estimate
- Menu category pills (horizontal scroll)
- 3-4 menu item cards with icons, descriptions, prices, and Add buttons
- Cart summary section (hidden initially, shown when items added)
- "Confirm Order" CTA button

SCREEN 3 — REWARDS/LOYALTY:
- Points balance display (large number)
- Progress bar to next reward
- Recent activity / points history
- Available rewards list

SCREEN 4 — PROFILE:
- User name and role display
- Stats grid (orders today, rating, revenue)
- Settings options list
- Sign out button

═══════════════════════════════════════════════════════════
JAVASCRIPT REQUIREMENTS:
═══════════════════════════════════════════════════════════

- Tab navigation: clicking bottom nav icons switches screens (show/hide divs)
- Active tab highlighting (colored icon + label for active tab)
- Add to cart functionality with cart counter badge
- Cart total calculation
- Order confirmation alert
- Keep JS minimal and inline — no external libraries

═══════════════════════════════════════════════════════════
QUALITY GATE:
═══════════════════════════════════════════════════════════

The output MUST be at least 200 lines of HTML. If your response would be shorter, ADD MORE DETAIL:
- More menu items, more sections, richer styling, more interactive elements.
- The person seeing this demo should think: "Wow, they built this JUST for my business."

REMEMBER: This is a SALES TOOL. The prospect must be impressed. Generic = failure. Personalized = sale."""


def _extract_html(text: str) -> str:
    """Extracts HTML content if the LLM accidentally wraps it in markdown."""
    text = (text or "").strip()
    # Try extracting from markdown fences first
    match = re.search(r"```html\s*\n(.*?)\n\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Try any code fence
    match = re.search(r"```\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if match and "<!DOCTYPE" in match.group(1).upper():
        return match.group(1).strip()
    return text.strip()


def _validate_html(html: str, business_name: str) -> bool:
    """Basic validation that the output is a real, high-quality HTML demo."""
    if not html:
        return False
    html_upper = html.upper()
    if "<!DOCTYPE" not in html_upper:
        return False
    if len(html) < 3000:  # Minimum ~100 lines of meaningful HTML
        logger.warning(f"Demo for {business_name} is too short ({len(html)} chars) — low quality")
        return False
    if business_name.lower() not in html.lower():
        logger.warning(f"Demo for {business_name} doesn't contain the business name")
        return False
    return True


def _build_demo_request(business_name: str, research_data: dict) -> str:
    """Build a rich user message with ALL research data for the demo agent."""
    
    founder_name = research_data.get("decision_maker_name", "Not Found")
    if founder_name in ["Not Found", "Unknown", "", None]:
        founder_name = "Manager"
    
    has_app = research_data.get("has_mobile_app", "No")
    website = research_data.get("website", "Not Found")
    
    # Determine what to build
    if has_app in ["No", "Not Found", None, ""]:
        build_type = "a native-looking iOS Mobile App prototype"
    elif website in ["Not Found", "No", None, ""]:
        build_type = "a beautiful mobile-responsive Landing Page"
    else:
        build_type = "a 'Next Generation' iOS App that solves their specific pain points"
    
    pain_1 = research_data.get("top_pain_theme_1", "Operational inefficiency")
    pain_2 = research_data.get("top_pain_theme_2", "Weak digital presence")
    pain_3 = research_data.get("top_pain_theme_3", "No customer retention system")
    
    what_love = research_data.get("what_customers_love", "Great service and quality")
    sample_quote = research_data.get("sample_review_quote", "")
    demo_angle = research_data.get("demo_angle", "Modern digital solution for operational efficiency")
    business_type = research_data.get("business_type", "Business")
    google_rating = research_data.get("google_rating", "")
    location = research_data.get("location", "")
    
    # Get actual menu items / products from reviews if available
    reviews = research_data.get("reviews", [])
    reviews_text = ""
    if reviews:
        reviews_text = "\n".join(f'  - "{r}"' for r in reviews[:5])
    
    msg = f"""Build {build_type} for this specific business:

══════════════════════════════════════
BUSINESS IDENTITY:
══════════════════════════════════════
- Name: {business_name} (MUST be prominently displayed everywhere)
- Type: {business_type}
- Location: {location}
- Google Rating: {google_rating}
- Founder/Manager: {founder_name}
  → Personalize welcome: "Welcome back, {founder_name}!" or "Admin Dashboard for {founder_name}"

══════════════════════════════════════
WHAT CUSTOMERS LOVE (feature these!):
══════════════════════════════════════
{what_love}
→ Turn these into featured sections, recommended items, and highlight cards.

══════════════════════════════════════
PAIN POINTS (the UI MUST solve these):
══════════════════════════════════════
1. {pain_1} → Add a prominent UI solution (e.g., if "long wait times" → "Skip the Line" button)
2. {pain_2} → Add a relevant feature/section
3. {pain_3} → Add a relevant feature/section

══════════════════════════════════════
DEMO ANGLE (core value proposition):
══════════════════════════════════════
{demo_angle}

══════════════════════════════════════
REAL CUSTOMER REVIEW (embed as social proof):
══════════════════════════════════════
"{sample_quote}"

══════════════════════════════════════
ACTUAL REVIEWS (extract product names/items from these for the menu):
══════════════════════════════════════
{reviews_text if reviews_text else "No specific reviews available — use business type to infer likely products."}

══════════════════════════════════════
Generate the complete HTML now. Start with <!DOCTYPE html>."""

    return msg


async def build_demo_for_lead(business_name: str, research_data: dict) -> str:
    """
    Takes research data and generates a high-fidelity HTML mockup.
    Returns the file path of the generated demo.
    """
    
    # Ensure demos directory exists
    os.makedirs("demos", exist_ok=True)
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', business_name).lower()
    file_path = f"demos/{safe_name}_demo.html"

    # If demo already exists, don't regenerate (saves credits/time)
    if os.path.exists(file_path):
        logger.info(f"Demo already exists for {business_name}")
        return file_path

    logger.info(f"Building high-fidelity demo for: {business_name}")
    print(f"  [DEMO] Generating personalized app mockup for {business_name}...")

    # Build the rich, data-packed user message
    user_message = _build_demo_request(business_name, research_data)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            model = get_agentrouter_model()
            agent = Agent(
                name="Demo Builder Agent",
                instructions=DEMO_SYSTEM_PROMPT,  # Generic system role
                model=model,
                model_settings=ModelSettings(
                    temperature=0.7,  # Creative but structured
                ),
            )
            
            # Pass ALL research data in the user message
            result = await Runner.run(agent, user_message)
            html_content = _extract_html(result.final_output)
            
            # Validate quality
            if _validate_html(html_content, business_name):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"  [DEMO] [SUCCESS] Saved: {file_path} ({len(html_content)} chars)")
                return file_path
            else:
                print(f"  [DEMO] [WARN] Attempt {attempt}: Low quality output ({len(html_content)} chars)")
                if attempt < max_attempts:
                    wait_time = 2 ** attempt
                    print(f"  [DEMO] [WAIT] Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif html_content:
                    # Save even if low quality on last attempt
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    return file_path

        except Exception as e:
            logger.error(f"Demo Agent Error (attempt {attempt}) for {business_name}: {e}")
            print(f"  [DEMO] [ERROR] Attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                wait_time = 2 ** attempt
                print(f"  [DEMO] [WAIT] Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                return "Failed to generate demo"

    return "Failed to generate demo"
