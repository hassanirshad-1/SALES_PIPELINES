import os
import time
import requests
from modules.utils import read_json, ensure_dir, write_json
from config import INSTANTLY_API_KEY, INSTANTLY_CAMPAIGN_ID, NETLIFY_PUBLIC_URL

def run_send(leads_path, screenshots_dir, limit=None):
    print("\n--- Starting Stage 4: Send via Instantly.ai ---")
    
    if not INSTANTLY_API_KEY or not INSTANTLY_CAMPAIGN_ID:
        print("❌ Error: Missing Instantly.ai credentials in .env")
        return

    if not NETLIFY_PUBLIC_URL:
        print("❌ Error: Missing NETLIFY_PUBLIC_URL in config.py or .env")
        return

    leads = read_json(leads_path)
    if not leads:
        print("❌ No leads found in JSON.")
        return

    if limit:
        leads = leads[:limit]
        print(f"Limiting to first {limit} leads.")

    success_count = 0
    failed_sends = []
    
    output_dir = os.path.dirname(screenshots_dir)
    ensure_dir(output_dir)

    for idx, lead in enumerate(leads):
        email = lead.get("email")
        if not email:
            continue
            
        slug = lead.get("slug")
        company = lead.get("company", "")
        name = lead.get("name", "there")
        niche = lead.get("niche", "business")
        
        # USE THE LIVE NETLIFY LINK
        demo_url = f"{NETLIFY_PUBLIC_URL.rstrip('/')}/{slug}/"
        
        # Email Body (HTML) - "THE DIRECT FLEX"
        body = f"""Hi {name},<br><br>
I built a <b>production-ready mobile app</b> prototype specifically for <b>{company}</b>. 🚀<br><br>
You can play with the live demo here: <a href="{demo_url}">{demo_url}</a><br><br>
It took me a bit to put together, but I wanted to show you exactly what's possible for your brand. If you like the vibe, I can have a full version ready to ship in 3 days.<br><br>
Worth a quick chat?<br><br>
Best,<br>
Hassan"""

        payload = {
            "api_key": INSTANTLY_API_KEY,
            "campaign_id": INSTANTLY_CAMPAIGN_ID,
            "email": email,
            "first_name": name,
            "company_name": company,
            "personalization": body
        }
        
        try:
            res = requests.post("https://api.instantly.ai/api/v1/lead/add", json=payload, timeout=10)
            if res.status_code == 200:
                print(f"📧 Sent to Instantly {idx+1}/{len(leads)} — {email}")
                success_count += 1
            else:
                print(f"❌ Failed to send to {email}: {res.text}")
                failed_sends.append({"email": email, "error": res.text})
        except Exception as e:
            print(f"❌ API Error for {email}: {e}")
            failed_sends.append({"email": email, "error": str(e)})
            
        time.sleep(0.5) # Rate limit

    if failed_sends:
        write_json(os.path.join(output_dir, "failed_sends.json"), failed_sends)

    print(f"Total sent: {success_count}")
    print(f"Failed: {len(failed_sends)}")
    print("--- Stage 4 Complete ---")
