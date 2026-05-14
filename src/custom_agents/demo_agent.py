import os
import json
import logging
import re
from src.config.models import get_agentrouter_model
from agents import Agent, Runner
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEMO_PROMPT_TEMPLATE = """You are an elite UI/UX designer and Frontend Engineer. 
Your task is to create a hyper-personalized, high-fidelity Mobile App Mockup or Landing Page (Single File HTML/CSS/JS) for a specific business.

DECISION LOGIC (WHAT TO BUILD):
- If the business has no mobile app (Has App: {has_app}), you MUST build a native-looking iOS Mobile App prototype.
- If the business has no website (Website: {website}), you MUST build a beautiful desktop/mobile responsive Landing Page.
- If they have both, build a "Next Generation" iOS App that specifically solves their pain points.

BUSINESS DETAILS:
- Name: {business_name} (MUST be prominently displayed)
- Type: {business_type}
- Decision Maker (Founder/Manager): {founder_name} (Personalize the welcome screen to them! e.g., "Welcome back, {founder_name}!" or "Admin Dashboard for {founder_name}")

WHAT CUSTOMERS LOVE:
{what_customers_love}
(Turn these into featured app/web sections. Use their exact favorite items!)

TOP PAIN POINTS (The UI MUST explicitly solve these):
1. {pain_1}
2. {pain_2}
3. {pain_3}
(For example: if pain is "long wait times", add a massive "Skip the Line" button. If the pain is "staff not knowledgeable", add a "Staff Training Module" or "Coffee Guide" section).

ACTUAL CUSTOMER REVIEW (Embed this somewhere in the UI as social proof or a problem to fix):
"{sample_quote}"

DEMO ANGLE (The core pitch/value proposition of this app):
{demo_angle}

STRICT TECHNICAL & DESIGN REQUIREMENTS:
1. APP UI, NOT A WEBSITE: The design MUST look exactly like a native iOS app. Use a centered mobile-sized container (max-w-md mx-auto h-screen relative overflow-hidden) with a fixed bottom navigation bar (Home, Order, Profile, etc.).
2. EXTREME PERSONALIZATION: Do not use generic text. Use "{business_name}" everywhere. If they love specific items (like cheesecake), put those items in the UI.
3. TAILWIND CSS: Use Tailwind via CDN (<script src="https://cdn.tailwindcss.com"></script>).
4. MODERN AESTHETICS: Use Apple-style design: rounded-3xl, large bold typography (font-sans font-bold tracking-tight), subtle gray backgrounds (bg-gray-50), and pure white cards with soft shadows (shadow-sm).
5. ICONS: Use FontAwesome CDN for bottom nav icons and UI icons (<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">).
6. KEEP IT CONCISE: Do NOT write massive custom CSS animations or huge inline SVGs. Rely on Tailwind utility classes. You must ensure the entire file (including JavaScript for the buttons) fits within your output limit.
7. OUTPUT: Return ONLY the raw HTML code. Do NOT wrap in ```html. Start immediately with <!DOCTYPE html>.

Write the complete, hyper-personalized HTML app mockup now:"""

def _extract_html(text: str) -> str:
    """Extracts HTML content if the LLM accidentally wraps it in markdown."""
    match = re.search(r"```html\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()

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

    founder_name = research_data.get("decision_maker_name", "Not Found")
    if founder_name in ["Not Found", "Unknown", ""]:
        founder_name = "Manager"

    prompt = DEMO_PROMPT_TEMPLATE.format(
        business_name=business_name,
        business_type=research_data.get("business_type", "Business"),
        has_app=research_data.get("has_mobile_app", "No"),
        website=research_data.get("website", "No"),
        founder_name=founder_name,
        what_customers_love=research_data.get("what_customers_love", "Great service"),
        pain_1=research_data.get("top_pain_theme_1", "Inefficiency"),
        pain_2=research_data.get("top_pain_theme_2", "Poor online presence"),
        pain_3=research_data.get("top_pain_theme_3", "Lack of customer retention"),
        sample_quote=research_data.get("sample_review_quote", "We love this place!"),
        demo_angle=research_data.get("demo_angle", "Modern digital solution")
    )

    try:
        model = get_agentrouter_model()
        agent = Agent(
            name="Demo Builder Agent",
            instructions=DEMO_PROMPT_TEMPLATE,
            model=model
        )
        
        result = await Runner.run(agent, f"Generate the demo for {business_name}")
        html_content = _extract_html(result.final_output)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        return file_path

    except Exception as e:
        logger.error(f"Demo Agent LLM Error for {business_name}: {e}")
        return "Failed to generate demo"

