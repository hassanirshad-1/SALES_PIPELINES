"""Main entry point for the Personalized Demo Generator & Bulk Outreach System."""
import argparse
import os
import sys

# Ensure modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from modules.ingest import run_ingest
from modules.generate import run_generate
from modules.deploy import run_deploy
from modules.host import run_host
from modules.send import run_send
from config import LEADS_INPUT_PATH, OUTPUT_DIR

def main():
    parser = argparse.ArgumentParser(
        description="Personalized Demo Generator & Bulk Outreach System"
    )

    # Pipeline stages
    parser.add_argument("--all", action="store_true", help="Run all pipeline stages")
    parser.add_argument("--ingest", action="store_true", help="Stage 1: Ingest leads from CSV")
    parser.add_argument("--generate", action="store_true", help="Stage 2: Generate demo HTMLs")
    parser.add_argument("--deploy", action="store_true", help="Stage 3: Screenshot + upload to R2")
    parser.add_argument("--host", action="store_true", help="Stage 3b: Host demos on Netlify (Free)")
    parser.add_argument("--send", action="store_true", help="Stage 4: Send emails via Instantly")
    parser.add_argument("--screenshots-only", action="store_true", help="Stage 3a: Screenshots only, no R2/Host")
    parser.add_argument("--limit", type=int, help="Process only first N leads (for testing)")

    args = parser.parse_args()

    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # File paths
    leads_clean = os.path.join(os.path.dirname(LEADS_INPUT_PATH) or "leads", "leads_clean.json")
    template_path = "template/index.html"

    # Stage 1
    if args.all or args.ingest:
        run_ingest(LEADS_INPUT_PATH, leads_clean)

    # Stage 2
    if args.all or args.generate:
        run_generate(leads_clean, template_path, OUTPUT_DIR, limit=args.limit)

    # Stage 3: Screenshot + R2 (Optional)
    if args.all or args.deploy or args.screenshots_only:
        upload = args.deploy and not args.screenshots_only
        run_deploy(OUTPUT_DIR, upload=upload, limit=args.limit)

    # Stage 3b: Netlify Hosting
    public_url = None
    if args.all or args.host:
        public_url = run_host(OUTPUT_DIR)

    # Stage 4
    if args.all or args.send:
        screenshots_dir = os.path.join(OUTPUT_DIR, "screenshots")
        # If we just hosted on Netlify, we should probably update the config or leads
        run_send(leads_clean, screenshots_dir, limit=args.limit)

    print("\n🎉 === PIPELINE COMPLETE === 🎉\n")

if __name__ == "__main__":
    main()
