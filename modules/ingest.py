import os
import re
import pandas as pd
from slugify import slugify
from modules.utils import write_json, ensure_dir

def run_ingest(input_path, output_path):
    print("\n--- Starting Stage 1: Ingest ---")
    if not os.path.exists(input_path):
        print(f"❌ Error: Input file not found at {input_path}")
        return

    try:
        if input_path.endswith('.xlsx'):
            df = pd.read_excel(input_path)
        else:
            df = pd.read_csv(input_path)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return

    # Lowercase and strip column headers
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Mapping logic for different CSV formats
    col_mapping = {
        'business_name': 'company',
        'contact_name': 'name',
        'contact_email': 'email',
        'business_type': 'niche',
        'address': 'city'
    }
    
    # Apply mapping if new columns exist
    for new_col, old_col in col_mapping.items():
        if new_col in df.columns and old_col not in df.columns:
            df[old_col] = df[new_col]

    # Required for the app to function
    required_cols = ['company', 'email', 'logo_url']
    for col in required_cols:
        if col not in df.columns:
            print(f"❌ Missing required column: {col}")
            print(f"Available columns: {list(df.columns)}")
            return

    # We will log skipped rows
    skipped_log = []
    valid_leads = []
    seen_slugs = set()

    for idx, row in df.iterrows():
        # Validate required
        missing = [col for col in required_cols if pd.isna(row[col]) or str(row[col]).strip() == ""]
        if missing:
            skipped_log.append(f"Row {idx+2}: Missing fields -> {', '.join(missing)}")
            continue

        email = str(row['email']).strip()
        # Basic regex: contains @ and a dot after
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            skipped_log.append(f"Row {idx+2}: Invalid email -> {email}")
            continue

        logo_url = str(row['logo_url']).strip()
        if not logo_url.startswith("http://") and not logo_url.startswith("https://"):
            skipped_log.append(f"Row {idx+2}: Invalid logo_url -> {logo_url}")
            continue

        company = str(row['company']).strip()
        base_slug = slugify(company)
        slug = base_slug
        counter = 2
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        seen_slugs.add(slug)

        # Extract city from address if it exists
        city_val = str(row.get('city', '')).strip() if pd.notna(row.get('city')) else ""
        if ',' in city_val:
            city_val = city_val.split(',')[0].strip()

        # Defaults for optional fields
        name_val = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else "Friend"
        if name_val == "" or name_val.lower() == "nan": name_val = "Friend"
        
        niche_val = str(row.get('niche', '')).strip() if pd.notna(row.get('niche')) else "Specialty Coffee"
        if niche_val == "" or niche_val.lower() == "nan": niche_val = "Specialty Coffee"

        lead = {
            "name": name_val,
            "company": company,
            "email": email,
            "logo_url": logo_url,
            "niche": niche_val,
            "city": city_val,
            "website": str(row.get('website_url', row.get('website', ''))).strip() if pd.notna(row.get('website_url', row.get('website'))) else "",
            "slug": slug
        }
        valid_leads.append(lead)

    # Save skipped log
    ensure_dir(os.path.dirname(output_path) or ".")
    skipped_path = os.path.join(os.path.dirname(output_path) or ".", "skipped_leads.log")
    if skipped_log:
        with open(skipped_path, "w", encoding="utf-8") as f:
            f.write("\n".join(skipped_log))

    write_json(output_path, valid_leads)

    print(f"Total rows processed: {len(df)}")
    print(f"Valid leads saved: {len(valid_leads)}")
    print(f"Skipped rows: {len(skipped_log)}")
    print("--- Stage 1 Complete ---")
