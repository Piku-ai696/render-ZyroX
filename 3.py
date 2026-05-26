import time
from datetime import datetime
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- CONFIG ---
URL = "https://ucgxzganknweqfucjqqw.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVjZ3h6Z2Fua253ZXFmdWNqcXF3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTE5OTczNywiZXhwIjoyMDk0Nzc1NzM3fQ.yEap0n7fCuy44Ox0YXZpj4_cf3wO7IS6oJWA6sk0GqY" 
 
supabase = create_client(URL, KEY)
BASE_URL = "https://hianime.ad"

def run_resilient_harvester():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"--- 🕒 Resilient Sync Started: {today} ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
    

        while True:
            # 1. FETCH NEXT TARGET
            response = supabase.table("5").select("*")\
                .or_(f"last_updated.is.null,last_updated.neq.{today}")\
                .limit(1).execute()

            if not response.data:
                print("\n✅ MISSION COMPLETE: All rows updated.")
                break

            anime = response.data[0]
            anime_id = anime['id']
            sub_count = int(anime.get('s/ep/c') or 0)
            dub_count = int(anime.get('d/ep/c') or 0)
            existing_sub = anime.get('s_eps') or []
            existing_dub = anime.get('d_eps') or []

            # Determine ranges
            start_ep = min(len(existing_sub), len(existing_dub)) + 1
            max_target_ep = max(sub_count, dub_count)

            if start_ep > max_target_ep:
                print(f"⏩ {anime_id} already caught up. Marking date.")
                supabase.table("anime_list").update({"last_updated": today}).eq("id", anime_id).execute()
                continue

            print(f"\n📂 Syncing: {anime_id} ({existing_sub}/{sub_count}  {existing_dub}/{dub_count} ) (From Ep {start_ep})")

            new_sub_entries = []
            new_dub_entries = []

            for ep_num in range(start_ep, max_target_ep + 1):
                target_url = f"{BASE_URL}/watch/{anime_id}/ep-{ep_num}"
                print(f"  🎬 Scanning Ep {ep_num}...")

                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(4) # Wait for all server tabs (Sub, Dub, Raw, Hsub) to load

                    # --- SUB / HSUB / RAW LOGIC ---
                    if ep_num <= sub_count:
                        found_sub_link = ""
                        
                        # Step A: Try standard SUB
                        sub_el = page.query_selector('.servers-sub .item .btn:has-text("HD-1")')
                        if sub_el:
                            found_sub_link = sub_el.get_attribute('data-video')
                            print(f"    ✅ Found SUB")
                        
                        # Step B: Fallback to HSUB
                        if not found_sub_link:
                            hsub_el = page.query_selector('.servers-hsub .item .btn:has-text("HD-1")')
                            if hsub_el:
                                found_sub_link = hsub_el.get_attribute('data-video')
                                print(f"    🔄 Found HSUB Fallback")
                        
                        # Step C: Fallback to RAW
                        if not found_sub_link:
                            raw_el = page.query_selector('.servers-raw .item .btn:has-text("HD-1")')
                            if raw_el:
                                found_sub_link = raw_el.get_attribute('data-video')
                                print(f"    🔄 Found RAW Fallback")

                        new_sub_entries.append({"number": ep_num, "link": found_sub_link})
                        if not found_sub_link: print(f"    ⚠️ Saved Blank Sub")

                    # --- DUB LOGIC ---
                    if ep_num <= dub_count:
                        found_dub_link = ""
                        dub_el = page.query_selector('.servers-dub .item .btn:has-text("HD-1")')
                        if dub_el:
                            found_dub_link = dub_el.get_attribute('data-video')
                            print(f"    ✅ Found DUB")
                        
                        new_dub_entries.append({"number": ep_num, "link": found_dub_link})
                        if not found_dub_link: print(f"    ⚠️ Saved Blank Dub")

                except Exception as e:
                    print(f"    ❌ Error Ep {ep_num}: {e}")
                    break

            # 3. MERGE, SORT AND SAVE
            final_sub = sorted(existing_sub + new_sub_entries, key=lambda x: x['number'])
            final_dub = sorted(existing_dub + new_dub_entries, key=lambda x: x['number'])

            supabase.table("5").update({
                "s_eps": final_sub,
                "d_eps": final_dub,
                "last_updated": today
            }).eq("id", anime_id).execute()
            
            print(f"💾 Updated {anime_id}. Total: {len(final_sub)} Subs, {len(final_dub)} Dubs.")

        browser.close()

if __name__ == "__main__":
    run_resilient_harvester()
