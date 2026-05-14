import argparse
import sys
import io
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

import asyncio
import json
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pandas as pd
from src.config.columns import OUTPUT_COLUMNS, normalize_input_row
from src.custom_agents.research_agent import research_lead_row
from src.custom_agents.demo_agent import build_demo_for_lead
from src.custom_agents.outreach_agent import write_outreach_email

def _load_leads_table(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)

def _spreadsheet_row(result: dict) -> dict:
    return {col: result.get(col, "") for col in OUTPUT_COLUMNS}

def _empty_failed_row(business_name: str) -> dict:
    row = {col: "Not Found" for col in OUTPUT_COLUMNS}
    row["Business Name"] = business_name or "Not Found"
    row["Demo URL"] = ""
    row["Outreach Message"] = ""
    row["Research Status"] = "Failed"
    return row

async def _run(args: argparse.Namespace) -> None:
    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found.")
        return

    df = _load_leads_table(args.input)
    if args.limit > 0:
        df = df.head(args.limit)
    
    rows_for_sheet: list[dict] = []
    bundle: list[dict] = []

    print(f"Loaded {len(df)} leads from {args.input}")

    for idx, row in df.iterrows():
        raw = {str(k): row[k] for k in row.index}
        lead = normalize_input_row(raw)
        business_name = (lead.get("business_name") or "").strip() or f"Row {idx + 1}"

        print(f"\n{'='*60}")
        print(f"[{idx + 1}/{len(df)}] 🔍 Researching: {business_name}")
        print(f"{'='*60}")

        try:
            result = await research_lead_row(lead)
            
            # Prepare agent JSON for downstream agents
            agent_json = result.get("_raw_agent_json", {})
            
            # CRITICAL: Ensure business_name is ALWAYS in agent_json
            # Downstream agents (demo + outreach) need this to personalize output
            agent_json["business_name"] = business_name
            
            demo_path = ""
            email_copy = ""
            sheet = _spreadsheet_row(result)
            sheet["Business Name"] = business_name
            
            if agent_json.get("research_status") != "Failed":
                # RUN DEMO AGENT
                print(f"\n  📱 Building demo for {business_name}...")
                demo_path = await build_demo_for_lead(business_name, agent_json)
                
                # RUN OUTREACH AGENT
                print(f"\n  ✉️  Writing outreach for {business_name}...")
                email_copy = await write_outreach_email(agent_json, demo_path)
            else:
                print(f"  ⚠️  Research failed — skipping demo & outreach")
            
            sheet["Demo URL"] = demo_path
            sheet["Outreach Message"] = email_copy
            
            rows_for_sheet.append(sheet)
            bundle.append(
                {
                    "business_name": sheet["Business Name"],
                    "spreadsheet_row": sheet,
                    "research_agent_json": agent_json,
                    "maps_scrape": result.get("_maps_json"),
                }
            )
            
            print(f"\n  ✅ {business_name} complete | Status: {sheet.get('Research Status', 'Unknown')}")
            
        except Exception as e:
            print(f"\n  ❌ [FAIL] {business_name}: {e}")
            fail = _empty_failed_row(business_name)
            rows_for_sheet.append(fail)
            bundle.append(
                {
                    "business_name": business_name,
                    "spreadsheet_row": fail,
                    "error": str(e),
                }
            )

        # Intermediate save
        out_df = pd.DataFrame(rows_for_sheet).reindex(columns=OUTPUT_COLUMNS, fill_value="Not Found")
        out_df.to_csv(args.output_csv, index=False, encoding="utf-8-sig")
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)

    pd.DataFrame(rows_for_sheet).reindex(columns=OUTPUT_COLUMNS, fill_value="Not Found").to_excel(
        args.output_xlsx,
        index=False,
    )

    ok = sum(1 for r in rows_for_sheet if r.get("Research Status") not in ("Failed",))
    print(f"\nPipeline complete.")
    print(f"  CSV:   {args.output_csv}")
    print(f"  XLSX:  {args.output_xlsx}")
    print(f"  JSON:  {args.output_json}")
    print(f"  Completed rows (non-Failed status): {ok}/{len(rows_for_sheet)}")

def main() -> None:
    p = argparse.ArgumentParser(description="Lead Research Agent — batch runner")
    p.add_argument("--input", default="data/leads.csv", help="Input .csv or .xlsx")
    p.add_argument("--output-csv", default="data/research_output.csv")
    p.add_argument("--output-xlsx", default="data/research_output.xlsx")
    p.add_argument("--output-json", default="data/research_results.json")
    p.add_argument("--limit", type=int, default=0, help="Limit number of leads to process")
    args = p.parse_args()
    asyncio.run(_run(args))

if __name__ == "__main__":
    main()
