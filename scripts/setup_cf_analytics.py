"""
Cloudflare Web Analytics (RUM) 사이트를 API로 생성한다.
GitHub Pages처럼 Cloudflare로 프록시 안 되는 사이트("gray-clouded")도
호스트명만 등록하면 무료로 방문자 통계(순방문자/페이지뷰/유입경로/국가/기기)를
쿠키 없이 수집해준다. 결과 스니펫을 콘솔에 출력하고 파일로도 저장.
"""
import os, sys, json, requests

CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
HOST = sys.argv[1] if len(sys.argv) > 1 else None
if not HOST:
    print("사용법: python setup_cf_analytics.py <호스트명>")
    sys.exit(1)

url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/rum/site_info"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {CF_API_TOKEN}"}

resp = requests.post(url, headers=headers, json={"host": HOST, "auto_install": False}, timeout=30)
if resp.status_code >= 400:
    print("생성 실패:", resp.status_code, resp.text)
    sys.exit(1)
site = resp.json()["result"]
print(f"등록 완료: {HOST}")

print("site_tag:", site.get("site_tag"))
snippet = site.get("snippet", "")
out_path = f"cf_analytics_snippet_{HOST.replace('.', '_').replace('/', '_')}.html"
with open(out_path, "w") as f:
    f.write(snippet)
print("스니펫 저장:", out_path)
print("---snippet---")
print(snippet)
