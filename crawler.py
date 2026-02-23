import asyncio
import datetime
import json
import os
import re
from playwright.async_api import async_playwright

DATA_FILE = "data.json"

async def crawl_hmall() -> list:
    """현대홈쇼핑 방송편성표를 크롤링하여 결과 리스트를 반환합니다."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.6 Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            is_mobile=True,
        )
        page = await context.new_page()

        url = "https://www.hmall.com/md/dpl/index?mainDispSeq=2&brodType=all"
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 접속 중: {url}")

        try:
            await page.goto(url, wait_until="load", timeout=120000)
            await asyncio.sleep(10)
        except Exception as e:
            print(f"❌ 접속 실패: {e}")
            await browser.close()
            return []

        # ── 날짜 탭 목록 수집 ────────────────────────────
        tab_info = await page.evaluate("""() => {
            let btns = Array.from(document.querySelectorAll('button'));
            return btns
                .filter(b => (b.innerText.includes('오늘') || /\\d+/.test(b.innerText)) && b.innerText.length < 15)
                .map(b => b.innerText.trim());
        }""")

        print(f"📅 발견된 날짜 탭: {len(tab_info)}개")

        # 오늘(또는 첫 번째)부터 시작
        start_idx = next((i for i, t in enumerate(tab_info) if "오늘" in t), 0)
        
        results = []

        # 상위 탭(날짜) 루프
        for i in range(start_idx, min(start_idx + 7, len(tab_info))):
            current_day_text = tab_info[i]
            clean_date = current_day_text.replace("\n", " ").strip()
            print(f"\n  📆 {clean_date} 수집 중...")

            try:
                button_label = current_day_text.split("\n")[0]
                await page.evaluate("""(label) => {
                    let btns = Array.from(document.querySelectorAll('button'));
                    let target = btns.find(b => b.innerText.includes(label));
                    if (target) target.click();
                }""", button_label)
                await asyncio.sleep(4)
            except Exception as e:
                print(f"  ⚠️ 탭 전환 실패: {e}")
                continue

            # 'TV쇼핑' 필터 적용
            try:
                await page.evaluate("""() => {
                    let btns = Array.from(document.querySelectorAll('button, a'));
                    let tvBtn = btns.find(b => b.innerText.trim() === 'TV쇼핑' || b.innerText.includes('TV쇼핑'));
                    if (tvBtn) tvBtn.click();
                }""")
                await asyncio.sleep(5)
            except: pass

            # 스크롤 및 수집
            day_results = {}
            current_state = {"lastDate": "오늘", "lastTime": "00:00"}
            
            scroll_count = 0
            stagnant_count = 0
            
            while scroll_count < 50:
                eval_result = await page.evaluate("""(state) => {
                    let items = [];
                    let containers = Array.from(document.querySelectorAll('[data-time], ._1jauv3p0'));
                    let lastDate = state.lastDate;
                    let lastTime = state.lastTime;

                    containers.forEach(container => {
                        let broadcastTime = container.getAttribute('data-time') || "";
                        if (broadcastTime && broadcastTime.includes(' ')) broadcastTime = broadcastTime.split(' ')[1];
                        
                        if (!broadcastTime) {
                            let tMatch = container.innerText.match(/(\\d{1,2}:\\d{2})/);
                            if (tMatch) broadcastTime = tMatch[1];
                        }
                        
                        let currentDate = null;
                        let dMatch = container.innerText.match(/(\\d{1,2}월\\s*\\d{1,2}일)/);
                        if (dMatch) currentDate = dMatch[1];
                        else if (container.innerText.includes("내일")) currentDate = "내일";
                        else if (container.innerText.includes("오늘")) currentDate = "오늘";
                        else if (container.innerText.includes("어제")) currentDate = "어제";

                        if (broadcastTime) {
                            // Normalize time to HH:mm (e.g. 6:00 -> 06:00)
                            let [h, m] = broadcastTime.split(':');
                            lastTime = h.padStart(2, '0') + ":" + m.padStart(2, '0');
                        }
                        if (currentDate) lastDate = currentDate;

                        let links = Array.from(container.querySelectorAll('a[href*="slitmCd="], [data-slitm-cd]'));
                        links.forEach(l => {
                            let code = l.getAttribute('data-slitm-cd');
                            if (!code) {
                                let match = l.href ? l.href.match(/slitmCd=(\\d+)/) : null;
                                if (match) code = match[1];
                            }
                            if (!code) return;

                            let name = l.innerText.trim().split('\\n')[0].replace(/\\d+%.*/, '').trim();
                            if (name.length >= 2) {
                                items.push({ time: lastTime, code, name, itemDate: lastDate });
                            }
                        });
                    });
                    return { items, lastDate, lastTime };
                }""", current_state)
                
                new_items = eval_result["items"]
                current_state["lastDate"] = eval_result["lastDate"]
                current_state["lastTime"] = eval_result["lastTime"]
                
                today = datetime.datetime.now()
                year = today.year
                for item in new_items:
                    raw_date = item["itemDate"]
                    dt_obj = today
                    
                    if raw_date == "오늘": dt_obj = today
                    elif raw_date == "내일": dt_obj = today + datetime.timedelta(days=1)
                    elif "월" in raw_date:
                        m = re.search(r"(\d+)월", raw_date)
                        d = re.search(r"(\d+)일", raw_date)
                        if m and d:
                            dt_obj = datetime.datetime(year, int(m.group(1)), int(d.group(1)))
                    
                    final_date = dt_obj.strftime("%Y-%m-%d")
                    
                    key = (final_date, item["time"], item["code"])
                    day_results[key] = {
                        "date": final_date,
                        "time": item["time"],
                        "code": item["code"],
                        "name": item["name"]
                    }

                scroll_count += 1
                prev_h = await page.evaluate("document.body.scrollHeight")
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1.5)
                new_h = await page.evaluate("document.body.scrollHeight")
                
                if new_h == prev_h: stagnant_count += 1
                else: stagnant_count = 0
                if stagnant_count >= 10: break

            results.extend(day_results.values())
            print(f"  ✔ {len(day_results)}개 수집 완료")

        await browser.close()
        return results

def update_data_json(new_schedule):
    """data.json 파일을 읽어서 우리 재고와 매칭되는 상품만 schedule에 등록합니다."""
    if not os.path.exists(DATA_FILE):
        print(f"❌ {DATA_FILE} 파일을 찾을 수 없습니다.")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. 우리 재고(Items)에 있는 상품 코드 목록 추출
    our_codes = {str(item["code"]).strip() for item in data.get("items", [])}
    
    # 2. 크롤링 결과 중 우리 상품만 필터링
    filtered_schedule = [s for s in new_schedule if str(s["code"]).strip() in our_codes]
    
    # 3. 데이터 업데이트
    data["schedule"] = filtered_schedule
    
    # 4. 날짜 목록 추출 및 정렬 (전체 수집된 데이터 기준)
    # 우리 상품이 없더라도 '날짜 버튼'은 보이게 하여 크롤러가 작동함을 알림
    unique_dates = sorted(list(set([s["date"] for s in new_schedule])))
    data["dates"] = unique_dates
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ {DATA_FILE} 업데이트 완료! (필터링 적용)")
    print(f"📊 수집된 총 방송: {len(new_schedule)}개 -> 우리 상품 방송: {len(filtered_schedule)}개")
    if filtered_schedule:
        for s in filtered_schedule:
            print(f"   - [매칭] {s['date']} {s['time']} | {s['code']} | {s['name']}")
    else:
        print("   - ℹ️ 우리 재고와 일치하는 방송이 없습니다.")
    print(f"📅 대상 날짜: {', '.join(unique_dates)}")

async def main():
    print("=" * 50)
    print("  현대홈쇼핑 방송정보 자동 크롤러")
    print("=" * 50)

    results = await crawl_hmall()
    if results:
        update_data_json(results)
    else:
        print("⚠️ 수집된 방송 정보가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
