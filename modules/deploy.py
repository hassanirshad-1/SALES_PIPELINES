import os
import time
from playwright.sync_api import sync_playwright
from PIL import Image
import boto3
from config import R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET_NAME
from modules.utils import ensure_dir

def screenshot_demos(demos_dir, screenshots_dir, limit=None):
    print("\n--- Starting Stage 3a: Screenshots ---")
    ensure_dir(screenshots_dir)
    
    if not os.path.exists(demos_dir):
        print(f"❌ Error: Demos directory {demos_dir} not found.")
        return

    slugs = [d for d in os.listdir(demos_dir) if os.path.isdir(os.path.join(demos_dir, d))]
    if limit:
        slugs = slugs[:limit]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        success_count = 0
        for idx, slug in enumerate(slugs):
            html_path = os.path.abspath(os.path.join(demos_dir, slug, "index.html"))
            if not os.path.exists(html_path):
                continue
                
            file_url = f"file:///{html_path.replace('\\\\', '/')}"
            png_path = os.path.join(screenshots_dir, f"{slug}.png")
            
            try:
                page.goto(file_url, wait_until="networkidle")
                # Wait an extra second for images/fonts to load
                page.wait_for_timeout(1000)
                page.screenshot(path=png_path, full_page=True)
                
                # Resize to 600px wide
                with Image.open(png_path) as img:
                    w, h = img.size
                    ratio = 600 / w
                    new_h = int(h * ratio)
                    img = img.resize((600, new_h), Image.Resampling.LANCZOS)
                    img.save(png_path)
                    
                print(f"📸 Screenshot {idx+1}/{len(slugs)} — {slug}")
                success_count += 1
            except Exception as e:
                print(f"❌ Screenshot failed for {slug}: {e}")
                
        browser.close()
    
    print(f"Total screenshots generated: {success_count}")

def upload_to_r2(demos_dir, limit=None):
    print("\n--- Starting Stage 3b: R2 Upload ---")
    
    if not R2_ACCOUNT_ID or not R2_ACCESS_KEY or not R2_SECRET_KEY:
        print("❌ Error: Missing Cloudflare R2 credentials in .env")
        return

    s3 = boto3.client('s3',
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto"
    )

    slugs = [d for d in os.listdir(demos_dir) if os.path.isdir(os.path.join(demos_dir, d))]
    if limit:
        slugs = slugs[:limit]

    success_count = 0

    for idx, slug in enumerate(slugs):
        lead_dir = os.path.join(demos_dir, slug)
        files_to_upload = []
        
        # Collect files
        for root, dirs, files in os.walk(lead_dir):
            for file in files:
                files_to_upload.append(os.path.join(root, file))
                
        try:
            for file_path in files_to_upload:
                rel_path = os.path.relpath(file_path, lead_dir).replace('\\\\', '/')
                s3_key = f"{slug}/{rel_path}"
                
                content_type = "text/html"
                if file_path.endswith('.css'): content_type = "text/css"
                elif file_path.endswith('.png'): content_type = "image/png"
                elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'): content_type = "image/jpeg"
                elif file_path.endswith('.svg'): content_type = "image/svg+xml"
                
                with open(file_path, "rb") as f:
                    s3.put_object(
                        Bucket=R2_BUCKET_NAME,
                        Key=s3_key,
                        Body=f,
                        ContentType=content_type
                    )
            print(f"☁️ Uploaded {idx+1}/{len(slugs)} — {slug}")
            success_count += 1
        except Exception as e:
            print(f"❌ Upload failed for {slug}: {e}")
            
    print(f"Total uploaded: {success_count}")

def run_deploy(output_dir, upload=True, limit=None):
    demos_dir = os.path.join(output_dir, "demos")
    screenshots_dir = os.path.join(output_dir, "screenshots")
    
    screenshot_demos(demos_dir, screenshots_dir, limit=limit)
    if upload:
        upload_to_r2(demos_dir, limit=limit)
    print("--- Stage 3 Complete ---")
