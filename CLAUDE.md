# hyinventory — 현대홈쇼핑 PB 재고관리 (코드 지도)

> 작업 전에 이 파일을 먼저 읽고, 필요한 함수만 `grep -n "function 이름"`으로 찾아 그 부분만 읽을 것. index.html 전체를 읽지 말 것.
> 사용자: 한국어, 초보. 설명은 짧게. PR 만들면 바로 squash 병합 (`gh api` REST 사용, `gh pr create`는 막혀 있음).

## 전체 구조 (서버 없음)
- **index.html** (~2,500줄, HTML+CSS+JS 한 파일) → GitHub Pages: https://poodingcake-hue.github.io/hyinventory/
- **data.json** = DB. 브라우저가 GitHub Contents API로 읽고(익명), 씀(토큰 필요, localStorage `HY_GH_TOKEN`).
- **crawler.py** + `.github/workflows/daily_crawl.yml` → 매일 06:00 KST hmall 편성표 크롤링 → `schedule_all.json`(전체, 오늘 이후) + `data.json`의 schedule/dates(우리 상품만) 커밋.
- **images/<상품코드>.jpg** = 사용자가 올린 상품 이미지 (raw.githubusercontent.com 주소 + `?v=`).
- 레거시(안 씀): server.js, 실행하기.bat, package.json, node_modules, `API_BASE=localhost:3000`, runMigration. code.gs.txt = Google Apps Script(시트 백업, 이미지 프록시), config.json = GAS URL.
- 브랜치 feat/cloudflare-proxy: cloudflare/worker.js (토큰 숨기는 프록시, 미배포, 이미지 업로드 미지원). index.html의 `API_PROXY = ""`에 Worker URL 넣으면 토큰 입력 사라짐.

## data.json 구조
| 키 | 내용 |
|---|---|
| items[] | {code, brand, name, category, colors[], sizes[], image} |
| stockMap{} | `"코드_색상_사이즈": 수량` |
| rentals[] | {rowIndex, code, name, color, size, qty, renter, date, returnTime} (returnTime 비면 대여중) |
| outfits[] | {code, host(쇼호스트), size} 착장 정보 |
| handlings[] | {code, content, user} 취급 메모 |
| schedule[] / dates[] | 크롤러가 넣는 우리 상품 편성 (화면에선 applyLiveSchedule이 schedule_all.json으로 덮어씀) |
| variationsMap{}, brands[], categories[] | 현재 비어 있음 |

## 화면(탭) → 함수
**상단 탭**: switchMainView / internalSwitchView (view-inventory, view-schedule, view-register)

**재고관리 탭** (view-inventory)
- renderInventory: 카드 그리드, brandSearch/categorySearch 필터
- openDetail(code) / closeDetail: 상세 모달
  - updateRentalUI: 실시간 재고표(실재고 − 대여중), 대여 카트
  - addToCart / renderCart / clearCart / submitRental → callApi('processRental')
  - toggleRentalReturnButtons / submitReturn → callApi('processReturn')
  - openStockEdit / submitStockUpdate → callApi('saveInventoryData')
  - renderOutfitUI / openOutfitEdit / submitOutfitBatch / removeOutfit → 'batchSaveOutfits' / 'deleteOutfit'
  - saveHandlingNote → callApi('saveHandling')

**편성표 탭** (view-schedule)
- applyLiveSchedule: schedule_all.json 가져와 등록 상품과 매칭(오늘 이후) → DATA.schedule/dates
- renderDates / renderSchedule, parseTime

**상품등록 탭** (view-register)
- switchRegMode('new' | 'add'): 새 상품 등록 / 상품 추가 입고
- handleRegCodeInput: 코드 입력 시 기존 상품 불러오기(add), renderExistingStock
- updateRegMatrix: 색상×사이즈 수량 입력표 (.reg-stock-input)
- updateRegImage: 왼쪽 웹 이미지 + 클릭 시 `https://www.hmall.com/md/pda/itemPtc?slitmCd=코드` (reg-image-link)
- 내 이미지(오른쪽 칸 reg-custom-box): handleRegImageFile, resizeToJpegDataUrl(최대 1000px JPEG), showRegCustomImage, clearCustomImage, resetCustomBox, document paste/drop 리스너
- uploadImageToGithub(code, dataUrl) → images/코드.jpg
- submitRegistration → (내 이미지 있으면 업로드 먼저) → callApi('registerProductData')

**공통**
- refreshData → callApi('getInitialData') → applyLiveSchedule → initUI
- callApi(action, payload): data.json GET → action별 수정 → PUT. 401/403이면 토큰 지우고 재요청, 409는 동시수정 안내
- getToken / setToken / askToken, escHtml, showLoader
- 이미지: getHmallUrl, getImageUrls, tryLoadImages(여러 프록시 경쟁: wp.com/Google/DDG/weserv → GAS), loadViaProxy
- backupToSheets / confirmUpdateGithubFromDrive: 구글시트 백업/복원 (GAS 경유)

## crawler.py
- Playwright 모바일 뷰(390x844)로 https://www.hmall.com/md/dpl/index?mainDispSeq=2&brodType=all 스크롤 수집
- cleanName(JS): "구매하기/상담신청/방송중 상담가능/%/가격" 등 제외, 카드별 가장 그럴듯한 이름
- KST 기준 날짜, 180일 이상 과거면 +1년 보정
- write_schedule_all → schedule_all.json, update_data_json → data.json (우리 상품만)

## 주의
- 토큰을 코드에 넣지 말 것 (GitHub이 자동 폐기함).
- 셸에서 hmall/github.io curl 안 됨 → 확인은 브라우저 도구로. hmall 목록은 모바일 크기 + 보이는 창이어야 렌더링.
- 수정 후 문법 확인: `<script>` 내용 추출 → `node --check`.

## 할일 (2026-10-27)
1. 코드 입력 시 상품명 자동 채우기(schedule_all.json) + 이미 있는 코드 경고
2. 브랜드·카테고리 고르기 + 사이즈 세트 버튼
3. 편성표에 미등록 상품 표시 → 클릭 시 등록
4. Cloudflare Worker 배포로 토큰 입력 없애기
