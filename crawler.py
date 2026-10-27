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
        tab_info = await page.evaluate(r"""() => {
            let btns = Array.from(document.querySelectorAll('button'));
            return btns
                .filter(b => (b.innerText.includes('오늘') || /\d+/.test(b.innerText)) && b.innerText.length < 15)
                .map(b => b.innerText.trim());
        }""")

        print(f"📅 발견된 날짜 탭: {len(tab_info)}개")

        # 오늘 날짜 탭 클릭 (시작점)
        try:
            today_btn = page.get_by_role("button", name="오늘").first
            if await today_btn.count() > 0:
                await today_btn.click()
                print("  📆 '오늘' 탭에서 스크롤 수집 시작...")
                await asyncio.sleep(4)
        except Exception as e:
            print(f"  ⚠️ '오늘' 탭 클릭 실패 (진행 시도): {e}")

        # 'TV쇼핑' 필터 적용 (가능하다면)
        try:
            tv_btn = page.locator("button, a").filter(has_text=re.compile(r"^TV쇼핑$|^TV쇼핑\s"))
            if await tv_btn.count() > 0:
                await tv_btn.first.click()
                print("  📺 'TV쇼핑' 필터 적용됨")
                await asyncio.sleep(5)
        except: pass

        results_map = {}
        current_state = {"lastDate": "오늘", "lastTime": "00:00"}
        
        scroll_count = 0
        stagnant_count = 0
        total_items_captured = 0
        
        print("  ⏳ 무한 스크롤링 중 (날짜 자동 전환)...")
        
        while scroll_count < 100: # 충분히 스크롤
            try:
                eval_result = await page.evaluate(r"""(state) => {
                    const items = [];
                    const containers = Array.from(document.querySelectorAll('[data-time], ._1jauv3p0, .broadcast_item'));
                    let lastDate = state.lastDate;
                    let lastTime = state.lastTime;

                    containers.forEach(container => {
                        let broadcastTime = container.getAttribute('data-time') || "";
                        if (broadcastTime && broadcastTime.includes(' ')) {
                            broadcastTime = broadcastTime.split(' ')[1];
                        }
                        
                        if (!broadcastTime) {
                            const tMatch = container.innerText.match(/(\d{1,2}:\d{2})/);
                            if (tMatch) broadcastTime = tMatch[1];
                        }
                        
                        let currentDate = null;
                        const dMatch = container.innerText.match(/(\d{1,2}월\s*\d{1,2}일)/);
                        if (dMatch) {
                            currentDate = dMatch[1];
                        } else if (container.innerText.includes("내일")) {
                            currentDate = "내일";
                        } else if (container.innerText.includes("오늘")) {
                            currentDate = "오늘";
                        }

                        if (broadcastTime) {
                            const parts = broadcastTime.split(':');
                            lastTime = parts[0].padStart(2, '0') + ":" + parts[1].padStart(2, '0');
                        }
                        if (currentDate) lastDate = currentDate;

                        // 같은 상품코드 링크가 카드 안에 여러 개(이미지/상품명/구매하기/상담신청 등) 있으므로
                        // 코드별로 모아서 '상품명다운' 텍스트 하나만 고른다.
                        const JUNK_EXACT = /^(구매하기|상담신청|상담\s*신청|방송중\s*구매가능|구매\s*가능|Talk\s*참여|알리미|방송알리미|재입고알림|방송예정|더보기|LIVE|품절|매진|\d{1,3}\s*%|[\d,.\s]*원?)$/;
                        const cleanName = (raw) => {
                            const lines = (raw || "").split('\n').map(s => s.trim()).filter(Boolean);
                            for (let line of lines) {
                                if (JUNK_EXACT.test(line)) continue;
                                // 가격/버튼 텍스트가 이어붙은 경우 그 앞에서 자른다
                                line = line.replace(/\d{1,3}(,\d{3})+\s*원.*$/, "");
                                line = line.replace(/\s*\d{1,2}\s*%\s*$/, "");
                                line = line.replace(/(구매하기|상담신청|방송중\s*구매가능|알리미|재입고알림|방송예정|카카오\(현대\)|무료배송|판매가|할인가).*$/, "");
                                line = line.replace(/^\[?방송알리미\]?/, "").trim();
                                if (line.length >= 2 && !JUNK_EXACT.test(line)) return line;
                            }
                            return "";
                        };

                        const bestByCode = {};
                        const links = Array.from(container.querySelectorAll('a[href*="slitmCd="], [data-slitm-cd]'));
                        links.forEach(l => {
                            let code = l.getAttribute('data-slitm-cd');
                            if (!code) {
                                const match = l.href ? l.href.match(/slitmCd=(\d+)/) : null;
                                if (match) code = match[1];
                            }
                            if (!code) return;
                            const nm = cleanName(l.innerText || l.textContent || "");
                            // 가장 긴(=가장 상품명다운) 이름을 채택. 이름이 없어도 코드는 남긴다(재고 매칭은 코드 기준).
                            if (!(code in bestByCode) || nm.length > bestByCode[code].length) bestByCode[code] = nm;
                        });
                        Object.entries(bestByCode).forEach(([code, name]) => {
                            items.push({ time: lastTime, code, name, itemDate: lastDate });
                        });
                    });
                    return { items, lastDate, lastTime };
                }""", current_state)
            except Exception as e:
                print(f"  ❌ 수집 중 오류: {e}")
                break
            
            new_items = eval_result["items"]
            current_state["lastDate"] = eval_result["lastDate"]
            current_state["lastTime"] = eval_result["lastTime"]
            
            today = datetime.datetime.now()
            year = today.year
            found_new_in_scroll = False
            
            for item in new_items:
                raw_date = item["itemDate"]
                dt_obj = today
                if raw_date == "오늘": dt_obj = today
                elif raw_date == "내일": dt_obj = today + datetime.timedelta(days=1)
                elif "월" in raw_date:
                    m = re.search(r"(\d+)월", raw_date)
                    d = re.search(r"(\d+)일", raw_date)
                    if m and d: dt_obj = datetime.datetime(year, int(m.group(1)), int(d.group(1)))
                
                final_date = dt_obj.strftime("%Y-%m-%d")
                key = (final_date, item["time"], item["code"])
                if key not in results_map:
                    results_map[key] = {
                        "date": final_date,
                        "time": item["time"],
                        "code": item["code"],
                        "name": item["name"]
                    }
                    found_new_in_scroll = True
                    total_items_captured += 1
                elif len(item["name"]) > len(results_map[key]["name"]):
                    # 스크롤 중 이름이 비어 있던 항목이 나중에 정상 이름으로 잡히면 보완
                    results_map[key]["name"] = item["name"]

            scroll_count += 1
            prev_h = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollBy(0, 2000)")
            await asyncio.sleep(2)
            new_h = await page.evaluate("document.body.scrollHeight")
            
            if scroll_count % 10 == 0:
                print(f"  ... {scroll_count}회 스크롤됨 (현재까지 수집: {total_items_captured}개, 날짜: {current_state['lastDate']})")

            if new_h == prev_h and not found_new_in_scroll: stagnant_count += 1
            else: stagnant_count = 0
            if stagnant_count >= 10: break

        results = list(results_map.values())
        print(f"  ✔ 총 {len(results)}개 방송 정보 수집 완료")

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
    
    # 4. 날짜 목록 추출 및 정렬 (우리 상품이 있는 날짜만)
    unique_dates = sorted(list(set([s["date"] for s in filtered_schedule])))
    data["dates"] = unique_dates
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ {DATA_FILE} 업데이트 완료! (우리 상품 편성표만 반영)")
    print(f"📊 수집된 총 방송: {len(new_schedule)}개 -> 우리 상품 방송: {len(filtered_schedule)}개")
    if filtered_schedule:
        for s in filtered_schedule:
            print(f"   - [매칭] {s['date']} {s['time']} | {s['code']} | {s['name']}")
    else:
        print("   - ℹ️ 우리 재고와 일치하는 방송이 없습니다.")
    print(f"📅 대상 날짜 (편성됨): {', '.join(unique_dates)}")

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
