# 축산 라이브러리 (Livestock-Revolution-Second)

창고 재고 사진을 브랜드/품목명으로 검색해서 보는 아카이브 사이트.
현재 재고 여부와 무관하게 계속 쌓이는 "라이브러리" 개념 — 축산레이더(Livestock-Revolution)의
실시간 현황판과는 별개 프로젝트.

## 배포
https://jeruhe2-sketch.github.io/Livestock-Revolution-Second/ (main 브랜치 push하면 반영)

## 구조
- `index.html` — 검색창 + 브랜드 태그 + 사진 갤러리, 빌드 도구 없는 단일 정적 페이지
- `data/manifest.json` — 사진 항목 목록. 각 항목: `{ brand, name, part, notes, photos: [url, ...] }`
- `data/brands.json` — 축산레이더 창고데이터(`data/warehouse_stock.enc.json`)에서 추출한 공급사/브랜드
  36개 (검색 자동완성 태그용, 정보 재사용은 이름만 — 수량/재고 등은 안 가져옴)

## 사진 저장 — Cloudflare R2
사진 원본은 이 저장소에 넣지 않고 Cloudflare R2에 저장, `manifest.json`은 R2의 공개 URL만 참조.

**아직 안 된 것 (다음 단계):**
1. Cloudflare 계정에서 R2 버킷 생성 (예: `livestock-library`)
2. 버킷 공개 접근 켜기 (Public Development URL 또는 커스텀 도메인 연결)
3. 공개 URL 패턴을 `index.html`이나 업로드 스크립트에 반영
4. 사진 업로드 (R2 대시보드 드래그앤드롭 또는 업로드 스크립트)
5. `data/manifest.json`에 브랜드/품목명/사진 URL 등록

## 새 항목 추가 방법 (수동)
`data/manifest.json`에 아래 형태로 추가 후 커밋/푸시:
```json
{
  "brand": "SEARA",
  "name": "삼겹살",
  "part": "삼겹",
  "notes": "2026-09 입고분",
  "photos": [
    "https://<R2 공개 URL>/SEARA/samgyeop_01.jpg",
    "https://<R2 공개 URL>/SEARA/samgyeop_02.jpg"
  ]
}
```
