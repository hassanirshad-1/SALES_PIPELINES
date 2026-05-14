import logging
import os
from src.config.models import get_agentrouter_model
from agents import Agent, Runner, ModelSettings
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SYSTEM PROMPT — defines the agent's copywriting role and framework.
# The actual business data is injected into the user message.
# ---------------------------------------------------------------------------
OUTREACH_SYSTEM_PROMPT = """You are a world-class B2B Cold Email Copywriter specializing in the "Direct Flex" framework.

You write hyper-personalized, high-converting cold emails that feel hand-crafted and human — never AI-generated.

FRAMEWORK — "Direct Flex":
1. Subject Line: Short, casual, relevant (e.g., "idea for {name}", "question about your coffee")
2. Salutation: "Hi {name}," or "Hi team," if name unknown
3. The Hook (Line 1): A hyper-personalized compliment proving you actually researched them
4. The Pivot (Line 2): Point out a small friction point and offer a solution
5. The Flex (Line 3): Tell them you built a custom prototype specifically for them. Include the demo link.
6. The Ask (Line 4): Low-friction CTA (e.g., "Worth a chat?")

RULES:
- Tone: Casual, confident, B2B. NO corporate jargon.
- Length: Under 75 words for the body.
- Make it sound like a human wrote it in 2 minutes.
- ONLY output the email. No "Sure!" or "Here's the email:" preamble.

OUTPUT FORMAT:
Subject: [Subject Line]

[Email Body]"""


def _build_outreach_request(research_data: dict, demo_url: str) -> str:
    """Build a rich user message with all data the copywriter needs."""
    
    business_name = research_data.get("business_name", "your business")
    
    founder_name = research_data.get("decision_maker_name", "Not Found")
    if founder_name in ["Not Found", "Unknown", "", None]:
        founder_name = "there"
    
    what_love = research_data.get("what_customers_love", "your great service")
    pain_1 = research_data.get("top_pain_theme_1", "streamlining operations")
    pain_2 = research_data.get("top_pain_theme_2", "")
    demo_angle = research_data.get("demo_angle", "increasing revenue")
    sample_quote = research_data.get("sample_review_quote", "")
    outreach_hook = research_data.get("outreach_hook", "")
    google_rating = research_data.get("google_rating", "")
    
    demo_link = demo_url if demo_url and demo_url != "Failed to generate demo" else "[Demo Link]"
    
    msg = f"""Write a hyper-personalized "Direct Flex" cold email for this business:

BUSINESS: {business_name}
DECISION MAKER: {founder_name}
GOOGLE RATING: {google_rating}

WHAT CUSTOMERS LOVE ABOUT THEM:
{what_love}

THEIR KEY PAIN POINT (use as the hook):
{pain_1}
{f"Secondary pain: {pain_2}" if pain_2 and pain_2 != "Not Found" else ""}

REAL CUSTOMER QUOTE (reference if useful):
"{sample_quote}"

OUR SOLUTION ANGLE:
{demo_angle}

SUGGESTED HOOK:
{outreach_hook}

DEMO LINK (include in email):
{demo_link}

Write the email now. Start with "Subject:" immediately."""

    return msg


async def write_outreach_email(research_data: dict, demo_url: str) -> str:
    """
    Generates a personalized cold email using the research data and demo link.
    """
    business_name = research_data.get("business_name", "your business")
    
    logger.info(f"Writing Outreach Email for: {business_name}")
    print(f"  [OUTREACH] Writing cold email for {business_name}...")

    # Build the data-rich user message
    user_message = _build_outreach_request(research_data, demo_url)

    try:
        model = get_agentrouter_model()
        agent = Agent(
            name="Outreach Copywriter Agent",
            instructions=OUTREACH_SYSTEM_PROMPT,  # Generic system role
            model=model,
            model_settings=ModelSettings(
                temperature=0.8,  # Creative writing needs higher temp
            ),
        )
        
        # Pass ALL data in the user message
        result = await Runner.run(agent, user_message)
        email = result.final_output.strip()
        
        # Validate — make sure it's an actual email, not a "I need more info" response
        if "Subject:" not in email and "subject:" not in email.lower():
            logger.warning(f"Outreach for {business_name} didn't produce a proper email")
            # Try to salvage
            if len(email) > 50:
                email = f"Subject: idea for {business_name}\n\n{email}"
        
        print(f"  [OUTREACH] [SUCCESS] Email generated ({len(email)} chars)")
        return email
        
    except Exception as e:
        logger.error(f"Outreach Agent Error for {business_name}: {e}")
        print(f"  [OUTREACH] [ERROR] Failed: {e}")
        return "Failed to generate email."
