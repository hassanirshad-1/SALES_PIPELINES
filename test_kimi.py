import asyncio
import json
from src.custom_agents.demo_agent import build_demo_for_lead

async def test_kimi():
    print("Loading existing research data to save credits...")
    with open("data/research_results.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for item in data:
        business_name = item.get("business_name")
        agent_json = item.get("research_agent_json", {})
        
        if agent_json.get("research_status") != "Failed":
            print(f"\n--- Firing Kimi for {business_name} ---")
            demo_path = await build_demo_for_lead(business_name, agent_json)
            print(f"Success! Demo saved to: {demo_path}")

if __name__ == "__main__":
    asyncio.run(test_kimi())
