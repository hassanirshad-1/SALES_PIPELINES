import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
from agents import Agent, Runner, ItemHelpers, ModelSettings
from agents.tool import FunctionTool

from src.tools.search_tools import search_duckduckgo
from src.tools.maps_scraper import scrape_google_maps_reviews, find_founder_info, smart_web_search, batch_web_search
from src.tools.page_fetch import fetch_url_main_text
from src.config.models import get_agentrouter_model
from src.config.columns import OUTPUT_COLUMNS

load_dotenv()
os.environ["OPENAI_TRACING_DISABLED"] = "true"

# ---------------------------------------------------------------------------
# SYSTEM INSTRUCTIONS — defines WHO the agent is and HOW it should behave.
# The actual lead data is injected into the user message, not here.
# ---------------------------------------------------------------------------
RESEARCH_SYSTEM_PROMPT = """You are an elite Lead Research Agent specializing in deep-dive business intelligence for the GCC/MENA market and globally.

YOUR MISSION: Given a business lead, perform exhaustive multi-source research and return a COMPLETE, ACCURATE JSON dossier. You are judged on COMPLETENESS — every field matters.

═══════════════════════════════════════════════════════════
TOOL STRATEGY (ordered by cost — use cheapest first):
═══════════════════════════════════════════════════════════

1. `scrape_google_maps_reviews` — ALWAYS call this FIRST. It returns the official Google rating, address, phone, website, and real reviews. Pass `business_name` and `location_hint` if you have them.

2. `batch_web_search` — ⚡ PREFERRED for efficiency. Takes a LIST of queries and runs them ALL at once in parallel. Use this instead of calling `smart_web_search` multiple times. Example:
   batch_web_search(queries=["Business Instagram", "Business app mobile", "Business founder owner", "Business delivery Talabat"])
   This saves turns and is much faster.

3. `smart_web_search` — Use for SINGLE follow-up queries when you need one specific thing. It auto-cascades through free→paid search APIs.

3. `find_founder_info` — Specifically hunts for the Owner/Founder name and LinkedIn. ALWAYS call this.

4. `fetch_url_main_text` — Use when you find a specific URL (About page, Team page, Instagram profile) and need to extract detailed text content from it. Great for confirming founder names, reading menu pages, checking if online ordering exists.

═══════════════════════════════════════════════════════════
RESEARCH METHODOLOGY (follow this order):
═══════════════════════════════════════════════════════════

STEP 1 — BASELINE: Call `scrape_google_maps_reviews` with the business name + location.
           This gives you: rating, address, phone, website, and verbatim reviews.

STEP 2 — DIGITAL PRESENCE SCAN: Use `batch_web_search` with ALL these queries at once:
   batch_web_search(queries=[
     "{business_name} Instagram",
     "{business_name} {location} app mobile ordering",
     "{business_name} {location} delivery Talabat HungerStation DoorDash UberEats",
     "{business_name} founded established year",
     "{business_name} loyalty program rewards"
   ])
   This runs them ALL in parallel in a single tool call — very efficient!

STEP 3 — FOUNDER HUNT: Call `find_founder_info`. If it returns "Not Found", try:
   a) `smart_web_search` with "{business_name} founder owner CEO"
   b) If you found a website, call `fetch_url_main_text` on their About/Team page

STEP 4 — SOCIAL MEDIA DEPTH: If you found social URLs, use `fetch_url_main_text` on the Instagram/Facebook page to check:
   - Are they posting recently? (active vs inactive)
   - Any customer complaints in comments?
   - Brand tone and language

STEP 5 — COMPETITOR CONTEXT: Use `smart_web_search`:
   "{business_type} near {location} best" → find 2-3 competitors

STEP 6 — REVIEW ANALYSIS: From the reviews you got in Step 1:
   - Identify the top 3 pain themes (complaints, frustrations)
   - Extract 2-3 verbatim quotes per theme
   - Calculate rough sentiment (% positive / negative / neutral)
   - Note what customers love most
   - Detect the language of reviews (Arabic/English/Mixed)

STEP 7 — SYNTHESIZE: Combine everything into the JSON output.

═══════════════════════════════════════════════════════════
CRITICAL RULES:
═══════════════════════════════════════════════════════════

• NEVER hallucinate or guess. If you can't find data, use "Not Found".
• ALL review quotes MUST be real, verbatim text from actual reviews you received from tools.
• Arabic reviews: translate them to English for the quote field, note "Arabic" as original language.
• If fewer than 5 reviews found total, mark sentiment as "Insufficient Data".
• For Google Rating, format as: "4.2 ⭐ (340 reviews)" using actual data from scrape_google_maps_reviews.
• Use ALL your tools aggressively — make at least 5-6 tool calls per lead.
• For the demo_angle field: recommend a SPECIFIC feature that solves their #1 pain point.
• For the outreach_hook: write a 1-liner that references a real pain point + real positive quote.

═══════════════════════════════════════════════════════════
OUTPUT FORMAT — Return ONLY this JSON, nothing else:
═══════════════════════════════════════════════════════════

{
  "business_name": "Exact official name from Google",
  "business_type": "e.g. Specialty Coffee Roaster & Café",
  "location": "Full address from Google Maps",
  "business_age": "e.g. Est. 2018 or ~5 years or Not Found",
  "google_rating": "e.g. 4.2 ⭐ (340 reviews) — use real numbers",
  "peak_hours": "From Google Maps data or Not Found",
  "website": "URL or Not Found",
  "has_mobile_app": "Yes (App Store) / Yes (Play Store) / No / Not Found",
  "on_delivery_platforms": "e.g. Yes (Talabat, HungerStation) / No / Not Found",
  "has_online_ordering": "Yes (via website/app) / No / Not Found",
  "has_loyalty_program": "Yes (description) / No / Not Found",
  "social_media_found": "e.g. Instagram ✅, TikTok ✅, Facebook ❌, LinkedIn ✅",
  "social_media_activity": "Active (posts in last 30 days) / Inactive / Not Found",
  "social_comments_signals": "Summary of any complaints or notable feedback in social comments, or Not Found",
  "top_pain_theme_1": "Most frequent complaint theme from reviews",
  "top_pain_theme_2": "Second most frequent complaint theme",
  "top_pain_theme_3": "Third complaint theme or Not Found",
  "sample_review_quote": "Single best verbatim quote that shows their main pain point (translated to English if Arabic)",
  "original_quote_language": "Arabic / English / Mixed",
  "sentiment_score": "e.g. 70% positive / 20% negative / 10% neutral OR Insufficient Data",
  "what_customers_love": "Comma-separated list of praised aspects from reviews",
  "decision_maker_name": "Owner/Founder full name or Not Found",
  "decision_maker_contact": "LinkedIn URL, email, or phone — or Not Found",
  "competitor_intel": "1-2 sentences about key local competitors and their digital presence",
  "demo_angle": "Specific feature recommendation based on their #1 pain point",
  "outreach_hook": "One-liner opening that references a real pain point",
  "reviews": ["Array of top 5-10 verbatim review quotes found"],
  "research_status": "Done / Partial / Low Data"
}

Output ONLY the raw JSON object. No markdown fences. No explanation text."""


def _parse_json_object(text: str) -> dict:
    """Robustly extract a JSON object from LLM output."""
    t = (text or "").strip()
    # Strip markdown code fences
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
        t = re.sub(r"\s*```\s*$", "", t)
    # Find the outermost JSON object
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        return {"research_status": "Failed"}
    try:
        return json.loads(t[s : e + 1])
    except json.JSONDecodeError:
        # Try fixing common LLM issues: trailing commas, single quotes
        raw = t[s : e + 1]
        raw = re.sub(r",\s*([}\]])", r"\1", raw)  # remove trailing commas
        try:
            return json.loads(raw)
        except:
            return {"research_status": "Failed"}


def _build_user_message(lead: dict) -> str:
    """Build a rich user message that passes ALL known lead data to the agent."""
    business_name = lead.get("business_name") or lead.get("Business Name") or "Unknown"
    location = lead.get("location") or lead.get("Location") or ""
    
    parts = [f"Research this business lead thoroughly:\n"]
    parts.append(f"**Business Name**: {business_name}")
    
    if location:
        parts.append(f"**Location**: {location}")
    
    # Pass any pre-known data from the input CSV
    field_map = {
        "industry_hint": "Industry/Category Hint",
        "phone": "Phone Number",
        "whatsapp": "WhatsApp Number",
        "email": "Email Address",
        "linkedin_url": "LinkedIn URL",
        "google_maps_url": "Google Maps URL",
        "instagram_url": "Instagram URL",
        "facebook_url": "Facebook URL",
        "tiktok_url": "TikTok URL",
        "other_social_url": "Other Social URL",
        "contact_name": "Contact Name",
    }
    
    known_data = []
    for key, label in field_map.items():
        val = (lead.get(key) or "").strip()
        if val and val.lower() not in ("", "nan", "none", "not found"):
            known_data.append(f"  - {label}: {val}")
    
    if known_data:
        parts.append(f"\n**Pre-known data from our database** (use these to skip discovery steps):")
        parts.extend(known_data)
    
    parts.append(f"\nUse ALL your tools. Start with scrape_google_maps_reviews, then fan out to smart_web_search, find_founder_info, and fetch_url_main_text.")
    parts.append(f"Return the complete JSON dossier with ALL fields populated.")
    
    return "\n".join(parts)


async def research_lead_row(lead: dict) -> dict:
    business_name = lead.get("business_name") or lead.get("Business Name")
    location = (lead.get("location") or lead.get("Location") or "").strip()
    
    print(f"\n--- Researching: {business_name} ---")
    
    # Use SDK Agent with tools for autonomous research
    try:
        model = get_agentrouter_model()
        agent = Agent(
            name="Research Agent",
            instructions=RESEARCH_SYSTEM_PROMPT,
            model=model,
            tools=[scrape_google_maps_reviews, find_founder_info, smart_web_search, batch_web_search, fetch_url_main_text],
            model_settings=ModelSettings(
                temperature=0.1,  # Low temp for factual research
            ),
        )
        
        # Build a rich user message with ALL known lead data
        user_message = _build_user_message(lead)
        print(f"  [AGENT] [INFO] Starting autonomous research...")
        
        result = await Runner.run(agent, user_message, max_turns=25)
        agent_json = _parse_json_object(result.final_output)
        
        # Inject business_name into agent_json for downstream agents
        if "business_name" not in agent_json or agent_json["business_name"] == "Not Found":
            agent_json["business_name"] = business_name
            
    except Exception as e:
        print(f"  [AGENT ERROR] {e}")
        agent_json = {"research_status": "Failed", "business_name": business_name}

    # Map agent JSON keys to spreadsheet columns
    # The mapping: "Top Pain Theme 1" → "top_pain_theme_1"
    row = {}
    for col in OUTPUT_COLUMNS:
        key = col.lower().replace(" ", "_")
        row[col] = agent_json.get(key, "Not Found")
    
    # Determine research quality status
    status = agent_json.get("research_status", "Failed")
    filled_count = sum(
        1 for col in OUTPUT_COLUMNS
        if row.get(col) not in ("Not Found", "", None)
        and col not in ("Demo URL", "Outreach Message", "Research Status")
    )
    total_fields = len(OUTPUT_COLUMNS) - 3  # exclude Demo URL, Outreach Message, Research Status
    
    if status == "Failed" or filled_count < 3:
        row["Research Status"] = "Failed"
    elif filled_count < 8:
        row["Research Status"] = "Low Data"
    elif filled_count < 15:
        row["Research Status"] = "Partial"
    else:
        row["Research Status"] = "Done"
    
    print(f"  [RESULT] Status: {row['Research Status']} | Fields filled: {filled_count}/{total_fields}")
        
    row["_raw_agent_json"] = agent_json
    # Extract reviews from agent json if available
    row["_maps_json"] = {
        "reviews": [{"text": r, "source": "Agent Extracted"} for r in agent_json.get("reviews", [])]
    }
    return row

if __name__ == "__main__":
    asyncio.run(research_lead_row({"business_name": "Nightjar Coffee Roasters", "location": "Dubai"}))
