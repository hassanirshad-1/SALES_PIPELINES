import os
import subprocess
import json

def run_host(output_dir):
    print("\n--- Starting Stage 3b: Hosting (Netlify) ---")
    
    # We want to host the demos directory
    demos_dir = os.path.join(output_dir, "demos")
    
    if not os.path.exists(demos_dir):
        print(f"❌ Error: Demos directory not found at {demos_dir}")
        return None

    try:
        # Run netlify deploy
        # --json flag gives us parsable output
        # --prod makes it live
        print("🚀 Deploying to Netlify...")
        result = subprocess.run(
            ["netlify", "deploy", "--dir=" + demos_dir, "--prod", "--json"],
            capture_output=True,
            text=True,
            shell=True # Needed for Windows
        )

        if result.returncode != 0:
            if "login" in result.stderr.lower() or "login" in result.stdout.lower():
                print("🔑 Action Required: Please run 'netlify login' in your terminal first!")
            else:
                print(f"❌ Netlify Error: {result.stderr}")
            return None

        # Parse the JSON output to get the URL
        deploy_data = json.loads(result.stdout)
        site_url = deploy_data.get("site_url") or deploy_data.get("url")
        
        if site_url:
            print(f"✅ Success! Your demos are live at: {site_url}")
            return site_url
        else:
            print("⚠️ Deploy finished but couldn't find the site URL in output.")
            return None

    except Exception as e:
        print(f"❌ Hosting Error: {e}")
        return None
