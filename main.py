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
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pandas as pd
from src.config.columns import OUTPUT_COLUMNS, normalize_input_row
from src.custom_agents.research_agent import research_lead_row
from src.custom_agents.demo_agent import build_demo_for_lead
from src.custom_agents.outreach_agent import write_outreach_email
from src.deploy.netlify import deploy_demos, get_demo_url

# ═══════════════════════════════════════════════════════════
# CONCURRENCY SETTINGS
# ═══════════════════════════════════════════════════════════
# Max leads to process at the same time.
# 3 is safe for most APIs. Increase to 5 if you're not hitting rate limits.
MAX_CONCURRENT = 3


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


async def _process_single_lead(
    idx: int,
    total: int,
    lead: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """
    Process a single lead through the full pipeline:
    Research → Demo → Outreach
    
    The semaphore limits how many leads run at the same time.
    """
    business_name = (lead.get("business_name") or "").strip() or f"Row {idx + 1}"
    
    async with semaphore:
        print(f"\n{'='*60}")
        print(f"[{idx}/{total}] 🔍 Processing: {business_name}")
        print(f"{'='*60}")
        
        start = time.time()
        
        try:
            # STEP 1: RESEARCH
            result = await research_lead_row(lead)
            agent_json = result.get("_raw_agent_json", {})
            agent_json["business_name"] = business_name
            
            demo_url = ""
            email_copy = ""
            sheet = _spreadsheet_row(result)
            sheet["Business Name"] = business_name
            
            if agent_json.get("research_status") != "Failed":
                # STEP 2: DEMO
                print(f"  [{business_name}] 📱 Building demo...")
                demo_path = await build_demo_for_lead(business_name, agent_json)
                
                if demo_path and not demo_path.startswith("Failed"):
                    demo_url = get_demo_url(demo_path)
                else:
                    demo_url = demo_path or ""
                
                # STEP 3: OUTREACH
                print(f"  [{business_name}] ✉️  Writing outreach...")
                email_copy = await write_outreach_email(agent_json, demo_url)
            else:
                print(f"  [{business_name}] ⚠️  Research failed — skipping demo & outreach")
            
            sheet["Demo URL"] = demo_url
            sheet["Outreach Message"] = email_copy
            
            elapsed = time.time() - start
            status = sheet.get("Research Status", "Unknown")
            print(f"  [{business_name}] ✅ Done in {elapsed:.0f}s | Status: {status}")
            
            return {
                "success": True,
                "sheet": sheet,
                "bundle": {
                    "business_name": sheet["Business Name"],
                    "spreadsheet_row": sheet,
                    "research_agent_json": agent_json,
                    "maps_scrape": result.get("_maps_json"),
                },
            }
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"  [{business_name}] ❌ Failed after {elapsed:.0f}s: {e}")
            fail = _empty_failed_row(business_name)
            return {
                "success": False,
                "sheet": fail,
                "bundle": {
                    "business_name": business_name,
                    "spreadsheet_row": fail,
                    "error": str(e),
                },
            }


async def _run(args: argparse.Namespace) -> None:
    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found.")
        return

    df = _load_leads_table(args.input)
    if args.limit > 0:
        df = df.head(args.limit)
    
    total = len(df)
    concurrency = min(args.concurrency, total)
    
    print(f"\n{'='*60}")
    print(f"🚀 SALES PIPELINE — Processing {total} leads")
    print(f"   Concurrency: {concurrency} at a time")
    print(f"{'='*60}")
    
    # Prepare all leads
    leads = []
    for idx, row in df.iterrows():
        raw = {str(k): row[k] for k in row.index}
        leads.append(normalize_input_row(raw))
    
    # Process with semaphore-controlled concurrency
    semaphore = asyncio.Semaphore(concurrency)
    pipeline_start = time.time()
    
    tasks = [
        _process_single_lead(i + 1, total, lead, semaphore)
        for i, lead in enumerate(leads)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Collect results
    rows_for_sheet = []
    bundle = []
    
    for r in results:
        if isinstance(r, Exception):
            fail = _empty_failed_row("Unknown")
            rows_for_sheet.append(fail)
            bundle.append({"business_name": "Unknown", "spreadsheet_row": fail, "error": str(r)})
        else:
            rows_for_sheet.append(r["sheet"])
            bundle.append(r["bundle"])
    
    # Save outputs
    out_df = pd.DataFrame(rows_for_sheet).reindex(columns=OUTPUT_COLUMNS, fill_value="Not Found")
    out_df.to_csv(args.output_csv, index=False, encoding="utf-8-sig")
    out_df.to_excel(args.output_xlsx, index=False)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)

    # DEPLOY ALL DEMOS TO NETLIFY
    demo_count = sum(1 for r in rows_for_sheet if r.get("Demo URL", "").startswith("http"))
    if demo_count > 0:
        deploy_demos()
    else:
        print("\n  ⚠️  No demos to deploy")

    # FINAL SUMMARY
    pipeline_elapsed = time.time() - pipeline_start
    ok = sum(1 for r in rows_for_sheet if r.get("Research Status") not in ("Failed",))
    mins = pipeline_elapsed / 60
    
    print(f"\n{'='*60}")
    print(f"🏁 PIPELINE COMPLETE — {mins:.1f} minutes")
    print(f"{'='*60}")
    print(f"  📊 CSV:   {args.output_csv}")
    print(f"  📊 XLSX:  {args.output_xlsx}")
    print(f"  📊 JSON:  {args.output_json}")
    print(f"  ✅ Succeeded: {ok}/{total} leads")
    print(f"  ❌ Failed:    {total - ok}/{total} leads")
    print(f"  📱 Demos:     {demo_count} deployed")
    print(f"  🌐 Live at:   https://sales-pipeline-demos.netlify.app")
    print(f"  ⚡ Speed:     {pipeline_elapsed/total:.1f}s per lead (x{concurrency} concurrent)")

def main() -> None:
    p = argparse.ArgumentParser(description="Lead Research Agent — batch runner")
    p.add_argument("--input", default="data/leads.csv", help="Input .csv or .xlsx")
    p.add_argument("--output-csv", default="data/research_output.csv")
    p.add_argument("--output-xlsx", default="data/research_output.xlsx")
    p.add_argument("--output-json", default="data/research_results.json")
    p.add_argument("--limit", type=int, default=0, help="Limit number of leads to process")
    p.add_argument("--concurrency", type=int, default=MAX_CONCURRENT,
                   help=f"Max leads to process at once (default: {MAX_CONCURRENT})")
    args = p.parse_args()
    asyncio.run(_run(args))

if __name__ == "__main__":
    main()
