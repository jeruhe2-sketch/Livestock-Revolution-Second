"""
[GitHub Actions 크론에서 실행] WOAH ASF/가축전염병 이메일 알림 수집 스크립트

리프레시 토큰(GMAIL_REFRESH_TOKEN)으로 매번 새로 액세스 토큰을 발급받아 사용하므로
사람의 개입 없이 계속 자동 실행 가능합니다.

환경변수 (GitHub Secrets에서 주입):
  GMAIL_CLIENT_ID
  GMAIL_CLIENT_SECRET
  GMAIL_REFRESH_TOKEN

동작:
  1. WOAH에서 온 메일 중 아직 처리 안 한 것만 조회 (data/asf_alerts.json에 저장된
     last_processed_message_id 이후 것만)
  2. 제목/본문에서 국가명, 질병명, 날짜 파싱 (TODO: 실제 메일 포맷 확인 후 정규식 보정)
  3. 회사 공급사(SUPPLIER_COUNTRY_MAP)와 겹치는 국가면 긴급 표시
  4. data/asf_alerts.json 에 누적 저장
"""

import base64
import json
import os
import re
import sys
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

OUTPUT_PATH = "data/asf_alerts.json"

# WOAH 발신 주소 (실제 수신 메일 확인 후 정확한 주소로 교체 필요)
WOAH_SENDER_QUERY = "from:(woah.org OR oie.int)"

# 회사가 실제 거래 중인 원산지 - 겹치면 긴급 플래그
WATCH_COUNTRIES = {
    "spain": "스페인",
    "espana": "스페인",
    "brazil": "브라질",
    "brasil": "브라질",
}


def get_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())  # 리프레시 토큰으로 새 액세스 토큰 발급
    return build("gmail", "v1", credentials=creds)


def load_existing():
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_processed_message_id": None, "alerts": []}


def extract_text_from_message(msg: dict) -> str:
    """메일 본문(plain text) 추출. TODO: 실제 메일 구조(멀티파트 등) 보고 보정."""
    payload = msg.get("payload", {})
    parts = payload.get("parts", [payload])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def parse_alert(subject: str, body: str) -> dict:
    """제목/본문에서 국가·질병·날짜 추출. TODO: 실제 메일 포맷 확인 후 정규식 보정."""
    text = f"{subject}\n{body}".lower()

    matched_country = None
    for keyword, kr_name in WATCH_COUNTRIES.items():
        if keyword in text:
            matched_country = kr_name
            break

    disease = "ASF" if "african swine fever" in text or "asf" in text else "기타"

    return {
        "matched_country": matched_country,
        "disease": disease,
        "urgent": matched_country is not None,
    }


def main():
    state = load_existing()
    service = get_gmail_service()

    query = WOAH_SENDER_QUERY
    if state.get("last_processed_message_id"):
        # Gmail 검색 자체는 after:날짜 형태만 지원하므로,
        # 실제로는 message id 리스트를 받아 이미 처리한 것 이후만 거르는 방식으로 구현
        pass

    results = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
    messages = results.get("messages", [])

    new_alerts = []
    for m in messages:
        msg_id = m["id"]
        if msg_id == state.get("last_processed_message_id"):
            break  # 이미 처리한 지점까지 왔으면 중단

        full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
        subject = headers.get("Subject", "")
        body = extract_text_from_message(full)

        parsed = parse_alert(subject, body)
        new_alerts.append({
            "message_id": msg_id,
            "received_at": headers.get("Date", ""),
            "subject": subject,
            **parsed,
        })

    if new_alerts:
        state["alerts"] = new_alerts + state.get("alerts", [])
        state["last_processed_message_id"] = messages[0]["id"] if messages else state.get("last_processed_message_id")

    state["updated_at"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    urgent_count = sum(1 for a in new_alerts if a.get("urgent"))
    print(f"신규 알림 {len(new_alerts)}건 (긴급 {urgent_count}건) 저장 완료: {OUTPUT_PATH}")

    if urgent_count:
        # GitHub Actions 로그에서 눈에 띄게 표시 + 추후 Slack 등 연동 지점
        print("::warning::스페인/브라질 관련 ASF 알림 감지됨 - data/asf_alerts.json 확인 필요")


if __name__ == "__main__":
    main()
