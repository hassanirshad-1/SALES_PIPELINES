import logging
import os
from src.config.models import get_agentrouter_model
from agents import Agent, Runner
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OUTREACH_PROMPT_SYSTEM_PROMPT = """You are a world-class Sales Outreach Specialist.
Your task is to write a highly personalized, 'Direct Flex' style cold email.

CRITICAL RULES:
1. ONLY output the email text. No "Sure, I can do that" or "Here is the email".
2. DO NOT use fictional or placeholder data if you have real data.
3. Use the provided business details to make it feel 1-on-1.
4. Keep it short, punchy, and confident.
5. Format:
Subject: [Subject Line]

[Email Body]
"""

OUTREACH_PROMPT_TEMPLATE = """You are an elite B2B Cold Email Copywriter.
Write a hyper-personalized, high-converting cold email for {business_name}.

RESEARCH DATA:
- Decision Maker (Target): {founder_name}
- What they do well: {what_customers_love}
- Their Pain Point (The Hook): {pain_1}
- Our Solution Angle: {demo_angle}
- Demo Link: {demo_url}

EMAIL REQUIREMENTS (The "Direct Flex" Framework):
1. Subject Line: Keep it short, casual, and relevant (e.g., "idea for {business_name}", "question about your coffee", "{founder_name} / {business_name}").
2. Salutation: "Hi {founder_name}," or "Hi team," if name is unknown.
3. The Hook (Line 1): A hyper-personalized compliment about {what_customers_love}. Prove we actually researched them.
4. The Pivot (Line 2): Point out a small friction point ({pain_1}) and offer a solution.
5. The Flex (Line 3): Tell them we built a custom prototype specifically for them to solve it. Include the link: {demo_url}.
6. The Ask (Line 4): A low-friction Call to Action (e.g., "Worth a chat?").
7. Tone: Casual, confident, B2B. NO corporate jargon. Make it sound like it was written by a human in 2 minutes. Keep it under 75 words.

Output format:
Subject: [Subject Line]

[Email Body]
"""

async def write_outreach_email(research_data: dict, demo_url: str) -> str:
    """
    Generates a personalized cold email using the research data and demo link.
    """
    business_name = research_data.get("business_name", "your business")
    
    founder_name = research_data.get("decision_maker_name", "Not Found")
    if founder_name in ["Not Found", "Unknown", ""]:
        founder_name = "there"

    prompt = OUTREACH_PROMPT_TEMPLATE.format(
        business_name=business_name,
        founder_name=founder_name,
        what_customers_love=research_data.get("what_customers_love", "your great service"),
        pain_1=research_data.get("top_pain_theme_1", "streamlining operations"),
        demo_angle=research_data.get("demo_angle", "increasing revenue"),
        demo_url=demo_url if demo_url else "[Insert Demo Link Here]"
    )

    logger.info(f"Writing Outreach Email for: {business_name}")

    try:
        model = get_agentrouter_model()
        agent = Agent(
            name="Outreach Copywriter Agent",
            instructions=OUTREACH_PROMPT_TEMPLATE,
            model=model
        )
        
        result = await Runner.run(agent, f"Write the email for {business_name}")
        return result.final_output.strip()
    except Exception as e:
        logger.error(f"Outreach Agent Error for {business_name}: {e}")
        return "Failed to generate email."

