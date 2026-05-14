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
from src.tools.maps_scraper import scrape_google_maps_reviews, find_founder_info, smart_web_search
from src.tools.page_fetch import fetch_url_main_text
from src.config.models import get_agentrouter_model
from src.config.columns import OUTPUT_COLUMNS

load_dotenv()
os.environ["OPENAI_TRACING_DISABLED"] = "true"

RESEARCH_INSTRUCTIONS = """You are an elite Lead Research Agent specializing in the GCC/MENA market.
Your objective is to find high-fidelity data about a business and its owner while being EXTREMELY SMART about API credit usage.

TOOL STRATEGY:
1. `smart_web_search`: Use this for general queries. It automatically handles fallbacks (DDG -> SearchAPI -> Tavily -> Exa -> Serper) to save the most expensive credits for last.
2. `scrape_google_maps_reviews`: Use this to get the official ground truth for a physical location (rating, address, phone, website, and reviews).
3. `find_founder_info`: Use this specifically to hunt for the Owner/Founder name and LinkedIn profile.
4. `fetch_url_main_text`: Use this if you find a specific "About Us" or "Team" page URL and need to extract deeper founder details.

STEPS:
1. Start with `scrape_google_maps_reviews` to get the baseline.
2. Use `find_founder_info`.
3. If founder info is missing, use `smart_web_search` or `fetch_url_main_text` on the business website.
4. Combine all data into the required JSON format.

JSON SCHEMA (ALL KEYS MANDATORY):
{
  "business_type": "string",
  "location": "string",
  "website": "URL",
  "decision_maker_name": "FOUNDER/OWNER NAME",
  "decision_maker_contact": "LinkedIn URL or Email",
  "top_pain_theme_1": "string",
  "top_pain_theme_2": "string",
  "top_pain_theme_3": "string",
  "sample_review_quote": "Verbatim quote",
  "sentiment_score": "string",
  "what_customers_love": "comma separated",
  "demo_angle": "string",
  "outreach_hook": "string",
  "reviews": ["List of top 5 verbatim review quotes found"],
  "research_status": "Done"
}

Output ONLY raw JSON. No markdown. No chatter."""

def _parse_json_object(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
        t = re.sub(r"\s*```\s*$", "", t)
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1: return {"research_status": "Failed"}
    try:
        return json.loads(t[s : e + 1])
    except:
        return {"research_status": "Failed"}

def _verified_review_texts(maps: dict) -> list[str]:
    return [r.get("text", "") for r in maps.get("reviews", []) if r.get("text")]

async def research_lead_row(lead: dict) -> dict:
    business_name = lead.get("business_name") or lead.get("Business Name")
    location = (lead.get("location") or lead.get("Location") or "").strip()
    
    print(f"\n--- Researching: {business_name} ---")
    
    # Use SDK Agent with tools for autonomous research
    try:
        model = get_agentrouter_model()
        agent = Agent(
            name="Research Agent",
            instructions=RESEARCH_INSTRUCTIONS,
            model=model,
            tools=[scrape_google_maps_reviews, find_founder_info, smart_web_search, fetch_url_main_text]
        )
        
        # Start the research loop
        query = f"Research this lead: {business_name} in {location}"
        result = await Runner.run(agent, query)
        agent_json = _parse_json_object(result.final_output)
    except Exception as e:
        print(f"  [AGENT ERROR] {e}")
        agent_json = {"research_status": "Failed"}

    # 4. Map to output format
    row = {}
    for col in OUTPUT_COLUMNS:
        key = col.lower().replace(" ", "_")
        row[col] = agent_json.get(key, "Not Found")
    
    # Specific fix for status
    if row.get("Decision Maker Name") != "Not Found" or (agent_json.get("sample_review_quote") and agent_json.get("sample_review_quote") != "Not Found"):
        row["Research Status"] = "Done"
    else:
        row["Research Status"] = "Low Data"
        
    row["_raw_agent_json"] = agent_json
    # Extract reviews from agent json if available
    row["_maps_json"] = {
        "reviews": [{"text": r, "source": "Agent Extracted"} for r in agent_json.get("reviews", [])]
    }
    return row

if __name__ == "__main__":
    asyncio.run(research_lead_row({"business_name": "Nightjar Coffee Roasters"}))
