import time
import re
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- CONFIG ---
URL = "https://ucgxzganknweqfucjqqw.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVjZ3h6Z2Fua253ZXFmdWNqcXF3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTE5OTczNywiZXhwIjoyMDk0Nzc1NzM3fQ.yEap0n7fCuy44Ox0YXZpj4_cf3wO7IS6oJWA6sk0GqY" 

supabase = create_client(URL, KEY)
BASE_URL = "https://hianime.ad"

def run_enrichment_scraper():
    print("🔍 Syncing precisely targeted counts, posters, and descriptions...")
    
    # Fetch targets (adjust your query as needed)
    response = supabase.table("20").select("id", "title").limit(1000).execute() 

    targets = response.data
    if not targets:
        print("✅ No targets found.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0...")
        page = context.new_page()

        # Block noise
        page.route("**/*.{png,jpg,jpeg,svg,css,woff2}", lambda route: route.abort())

        for anime in targets:
            anime_id = anime['id']
            target_url = f"{BASE_URL}/anime/{anime_id}"
            print(f"🌐 Processing: {anime['title']}")

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                
                # --- NEW TARGETED EXTRACTION ---
                
                # 1. Isolate the Stats Block
                stats_container = page.query_selector(".film-stats")
                sub_count = "0"
                dub_count = None

                if stats_container:
                    # Only look at the HTML inside this specific div
                    stats_html = stats_container.inner_html()
                    
                    sub_match = re.search(r'tick-sub">.*?</i>\s*(\d+)', stats_html, re.DOTALL)
                    dub_match = re.search(r'tick-dub">.*?</i>\s*(\d+)', stats_html, re.DOTALL)

                    if sub_match:
                        sub_count = sub_match.group(1)
                    if dub_match:
                        dub_count = dub_match.group(1)
                
                # 2. Poster & Description (Standard Selectors)
                poster_el = page.query_selector(".anisc-poster img")
                poster_url = poster_el.get_attribute("src") if poster_el else None

                desc_el = page.query_selector(".film-description .text")
                description_text = desc_el.inner_text().strip() if desc_el else None

                # --- DB UPDATE ---
                supabase.table("20").update({
                    "poster": poster_url,
                    "description": description_text,
                    "s/ep/c": sub_count,
                    "d/ep/c": dub_count
                }).eq("id", anime_id).execute()
                
                print(f"   ✅ Stats: Sub({sub_count}) Dub({dub_count if dub_count else 'N/A'})")

            except Exception as e:
                print(f"   🛑 Error on {anime_id}: {e}")
            
            time.sleep(1)

        browser.close()

if __name__ == "__main__":
    run_enrichment_scraper()
