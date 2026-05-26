import re
import time
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- CONFIG ---
URL = "https://ucgxzganknweqfucjqqw.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVjZ3h6Z2Fua253ZXFmdWNqcXF3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTE5OTczNywiZXhwIjoyMDk0Nzc1NzM3fQ.yEap0n7fCuy44Ox0YXZpj4_cf3wO7IS6oJWA6sk0GqY" 
 
supabase = create_client(URL, KEY)
BASE_URL = "https://hianime.ad"

def run_az_discovery():
    print("🧹 Syncing existing IDs for deduplication...")
    existing_data = supabase.table("22").select("id").execute()
    existing_ids = {row['id'] for row in existing_data.data}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0...")
        page = context.new_page()

        # Optimize speed
        page.route("**/*.{png,jpg,jpeg,svg,css,woff2}", lambda route: route.abort())

        for page_num in range(211, 221): 
            target_url = f"{BASE_URL}/az-list/all?page={page_num}"
            print(f"🌐 Loading: {target_url}")
            
            page.goto(target_url, wait_until="networkidle")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            raw_content = page.content()

            # Split by flw-item to handle each card individually
            cards = raw_content.split('<div class="flw-item">')[1:]
            print(f"📊 Total cards detected in HTML: {len(cards)}")

            new_count = 0
            for card_html in cards:
                # --- FIXED REGEX LOGIC ---
                
                # 1. ID Match (Stays the same)
                id_match = re.search(r'href="/anime/([^"]+)"', card_html)
                
                # 2. Title Match (FIXED: Look for content between title=" and " class="dynamic-name")
                # This handles titles that start with quotes like ""Bungaku Shoujo""
                title_match = re.search(r'title=(.*?) class="dynamic-name"', card_html)
                
                if id_match and title_match:
                    anime_id = id_match.group(1)
                    # Clean the title: remove leading/trailing quotes if the regex caught them
                    title = title_match.group(1).strip('"')

                    if anime_id in existing_ids:
                        print(f"✅ Already have: {title}")
                        continue

                    # 3. Sub/Dub (Flexible matching)
                    sub_match = re.search(r'tick-sub.*?</i>\s*(\d+)', card_html, re.DOTALL)
                    dub_match = re.search(r'tick-dub.*?</i>\s*(\d+)', card_html, re.DOTALL)

                    sub_count = sub_match.group(1) if sub_match else "0"
                    dub_count = dub_match.group(1) if dub_match else None

                    # 4. DB SAVE
                    try:
                        supabase.table("22").insert({
                            "id": anime_id,
                            "title": title,
                            "s/ep/c": sub_count,
                            "d/ep/c": dub_count
                        }).execute()
                        existing_ids.add(anime_id)
                        new_count += 1
                        print(f"✨ NEWLY SAVED: {title}")
                    except Exception as e:
                        print(f"⚠️ Error saving {anime_id}: {e}")
                else:
                    print("❌ Failed to parse a card (likely missing ID or Title tags)")

            print(f"🏁 Page {page_num} finished. Saved {new_count} new anime.")

        browser.close()

if __name__ == "__main__":
    run_az_discovery()
