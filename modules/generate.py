import os
import shutil
from jinja2 import Environment, FileSystemLoader
from modules.utils import read_json, ensure_dir
from config import DEMO_CLAIM_URL, R2_PUBLIC_URL

def run_generate(leads_path, template_path, output_dir, limit=None):
    print("\n--- Starting Stage 2: Generate ---")
    
    if not os.path.exists(leads_path):
        print(f"❌ Error: Clean leads file not found at {leads_path}")
        return

    leads = read_json(leads_path)
    if not leads:
        print("❌ No leads found in JSON.")
        return

    if limit:
        leads = leads[:limit]
        print(f"Limiting to first {limit} leads.")

    template_dir = os.path.dirname(template_path)
    template_file = os.path.basename(template_path)

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_file)

    demos_dir = os.path.join(output_dir, "demos")
    ensure_dir(demos_dir)

    success_count = 0

    for idx, lead in enumerate(leads):
        slug = lead.get("slug")
        if not slug:
            continue
            
        lead_dir = os.path.join(demos_dir, slug)
        ensure_dir(lead_dir)

        company = lead.get("company", "")
        name = lead.get("name", "")
        logo_url = lead.get("logo_url", "")
        niche = str(lead.get("niche", "")).lower()
        city = lead.get("city", "")

        claim_url = f"{DEMO_CLAIM_URL}?slug={slug}"
        demo_url = f"{R2_PUBLIC_URL}/{slug}" if R2_PUBLIC_URL else f"http://localhost/{slug}"

        try:
            html_content = template.render(
                company=company,
                name=name,
                logo_url=logo_url,
                niche=niche,
                city=city,
                demo_url=demo_url,
                claim_url=claim_url
            )

            # Write index.html
            with open(os.path.join(lead_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(html_content)

            # Copy style.css
            style_src = os.path.join(template_dir, "style.css")
            if os.path.exists(style_src):
                shutil.copy(style_src, os.path.join(lead_dir, "style.css"))

            # Copy assets directory if it exists and is not empty
            assets_src = os.path.join(template_dir, "assets")
            assets_dest = os.path.join(lead_dir, "assets")
            if os.path.exists(assets_src) and os.path.isdir(assets_src):
                if not os.path.exists(assets_dest):
                    shutil.copytree(assets_src, assets_dest)

            success_count += 1
            print(f"Generated demo {idx+1}/{len(leads)} — {slug}")

        except Exception as e:
            print(f"❌ Error generating demo for {slug}: {e}")

    print(f"Total demos generated: {success_count}")
    print("--- Stage 2 Complete ---")
