"""Spreadsheet column order for Lead Research Agent output (handoff v1.0)."""

OUTPUT_COLUMNS = [
    "Business Name",
    "Business Type",
    "Location",
    "Business Age",
    "Google Rating",
    "Peak Hours",
    "Website",
    "Has Mobile App",
    "On Delivery Platforms",
    "Has Online Ordering",
    "Has Loyalty Program",
    "Social Media Found",
    "Social Media Activity",
    "Social Comments Signals",
    "Top Pain Theme 1",
    "Top Pain Theme 2",
    "Top Pain Theme 3",
    "Sample Review Quote",
    "Original Quote Language",
    "Sentiment Score",
    "What Customers Love",
    "Decision Maker Name",
    "Decision Maker Contact",
    "Competitor Intel",
    "Demo Angle",
    "Outreach Hook",
    "Demo URL",
    "Outreach Message",
    "Research Status",
]

# Input CSV/XLSX headers may vary; normalize to canonical keys used in code.
INPUT_ALIASES = {
    "business name": "business_name",
    "name": "business_name",
    "location / city": "location",
    "location": "location",
    "city": "location",
    "industry / category hint": "industry_hint",
    "industry": "industry_hint",
    "category": "industry_hint",
    "contact name": "contact_name",
    "phone number": "phone",
    "whatsapp number": "whatsapp",
    "email address": "email",
    "linkedin url": "linkedin_url",
    "google maps url": "google_maps_url",
    "instagram url": "instagram_url",
    "facebook url": "facebook_url",
    "tiktok url": "tiktok_url",
    "other social url": "other_social_url",
}


def normalize_input_row(raw: dict) -> dict:
    """Map a spreadsheet row (any casing/headers) to canonical snake_case keys."""
    out: dict = {}
    for k, v in raw.items():
        if k is None or (isinstance(k, float) and str(k) == "nan"):
            continue
        key = str(k).strip()
        nk = key.lower().strip()
        canon = INPUT_ALIASES.get(nk)
        if canon is None:
            # snake_case fallback: "Business Name" -> business_name
            nk2 = nk.replace("/", " ").replace("  ", " ").strip()
            canon = INPUT_ALIASES.get(nk2) or nk2.replace(" ", "_")
        val = v
        if val is None or (isinstance(val, float) and str(val) == "nan"):
            val = ""
        else:
            val = str(val).strip()
        out[canon] = val
    return out
