import os
from dotenv import load_dotenv

load_dotenv()

# Cloudflare R2 Credentials
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "demos")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")

# Instantly.ai Credentials
INSTANTLY_API_KEY = os.getenv("INSTANTLY_API_KEY", "")
INSTANTLY_CAMPAIGN_ID = os.getenv("INSTANTLY_CAMPAIGN_ID", "")

# System Config
LEADS_INPUT_PATH = "FULL_DATA_FINAL.csv"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
DEMO_CLAIM_URL = os.getenv("DEMO_CLAIM_URL", "https://yoursite.com/claim")
NETLIFY_PUBLIC_URL = os.getenv("NETLIFY_PUBLIC_URL", "")
