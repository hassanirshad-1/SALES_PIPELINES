import asyncio
import json
import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.custom_agents.demo_agent import build_demo_for_lead
from src.custom_agents.outreach_agent import write_outreach_email

async def main():
    # Load the research results
    results_path = "data/research_results.json"
    if not os.path.exists(results_path):
        print(f"Error: {results_path} not found.")
        return

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Find Onyx Coffee Lab
    onyx_data = None
    for entry in data:
        if entry["business_name"] == "Onyx Coffee Lab":
            onyx_data = entry["research_agent_json"]
            break

    if not onyx_data:
        print("Error: Onyx Coffee Lab data not found in research results.")
        return

    business_name = "Onyx Coffee Lab"
    print(f"--- Generating Kimi Demo for {business_name} ---")
    
    # 1. Build Demo
    demo_path = await build_demo_for_lead(business_name, onyx_data)
    print(f"Demo Path: {demo_path}")

    # 2. Build Outreach
    if demo_path and demo_path != "Failed to generate demo":
        print(f"\n--- Generating Outreach for {business_name} ---")
        outreach = await write_outreach_email(onyx_data, demo_path)
        
        # Update the JSON file with the new demo link and outreach
        for entry in data:
            if entry["business_name"] == business_name:
                entry["spreadsheet_row"]["Demo URL"] = demo_path
                entry["spreadsheet_row"]["Outreach Message"] = outreach
                break
        
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("\nUpdated data/research_results.json")

if __name__ == "__main__":
    asyncio.run(main())
