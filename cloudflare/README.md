# Cloudflare Worker 프록시 설정 (한 번만)

사이트가 GitHub `data.json`을 읽고 저장할 때 이 Worker를 거칩니다. GitHub 토큰은 Worker 비밀값으로만 보관되어
브라우저/공개 저장소에 노출되지 않고, 사용자가 토큰을 입력할 필요가 없습니다.

1. Cloudflare 대시보드 → Workers & Pages → Create → Worker → 이름 `hyinventory-proxy` → Deploy
2. Edit code → `worker.js` 내용 전체를 붙여넣고 Deploy
3. Settings → Variables and Secrets → Add → Type: **Secret**, 이름 `GITHUB_TOKEN`,
   값: GitHub fine-grained 토큰 (hyinventory 저장소 하나, Contents: Read and write, 만료 없음)
4. Worker 주소(`https://hyinventory-proxy.<계정>.workers.dev`)를 `index.html`의 `API_PROXY`에 넣고 커밋
