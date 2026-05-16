"""
Deploy module — pushes the demos/ folder to Netlify after each batch.
Returns live URLs for each demo file.
"""
import os
import re
import subprocess
import logging

logger = logging.getLogger(__name__)

NETLIFY_SITE_ID = "32502cc6-3095-4550-b1b0-c9c4d2ebe3d6"
NETLIFY_BASE_URL = "https://sales-pipeline-demos.netlify.app"
DEMOS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "demos")


def get_demo_url(file_path: str) -> str:
    """Convert a local demo file path to its Netlify URL."""
    filename = os.path.basename(file_path)
    return f"{NETLIFY_BASE_URL}/{filename}"


def deploy_demos() -> str:
    """
    Deploy the entire demos/ folder to Netlify.
    Returns the production URL or an error string.
    """
    demos_dir = os.path.abspath(DEMOS_DIR)
    
    if not os.path.exists(demos_dir):
        logger.error(f"Demos directory not found: {demos_dir}")
        return "Failed — demos directory not found"
    
    # Count files
    files = [f for f in os.listdir(demos_dir) if f.endswith('.html')]
    if not files:
        logger.warning("No demo files to deploy")
        return "No demos to deploy"
    
    print(f"\n{'='*60}")
    print(f"🚀 DEPLOYING {len(files)} demos to Netlify...")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [
                "netlify", "deploy",
                "--dir", demos_dir,
                f"--site={NETLIFY_SITE_ID}",
                "--prod",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.path.dirname(demos_dir),
        )
        
        output = result.stdout + result.stderr
        
        if result.returncode == 0 and "Deploy is live" in output:
            print(f"  ✅ Deploy successful!")
            print(f"  🌐 Base URL: {NETLIFY_BASE_URL}")
            for f in files:
                print(f"     → {NETLIFY_BASE_URL}/{f}")
            return NETLIFY_BASE_URL
        else:
            logger.error(f"Deploy failed: {output[-500:]}")
            print(f"  ❌ Deploy failed: {output[-300:]}")
            return f"Deploy failed: {output[-200:]}"
            
    except FileNotFoundError:
        msg = "Netlify CLI not found. Install with: npm i -g netlify-cli"
        logger.error(msg)
        print(f"  ❌ {msg}")
        return msg
    except subprocess.TimeoutExpired:
        msg = "Deploy timed out after 120 seconds"
        logger.error(msg)
        print(f"  ❌ {msg}")
        return msg
    except Exception as e:
        logger.error(f"Deploy error: {e}")
        print(f"  ❌ Deploy error: {e}")
        return f"Deploy error: {e}"
