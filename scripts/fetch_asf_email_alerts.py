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
  2. 제목에서 국가코드·질병명·통보일자 파싱, 한글로 번역
     (실제 메일 제목 포맷: "{ISO3 국가코드} {DD/MM/YY} — {영어 질병명} / {불어} / {스페인어}",
      예: "SSD 18/09/26 — African swine fever / Peste porcine africaine / Peste porcina africana")
  3. 구독확인 메일 등 실제 질병 통보가 아닌 메일은 alerts 목록에서 제외(스킵)
  4. 회사 공급사(WATCH_COUNTRY_CODES, ISO3 코드 기준)와 겹치는 국가면 긴급 표시
  5. data/asf_alerts.json 에 누적 저장
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

# WOAH 발신 주소
# - woah-info-web@woah.org : WAHIS Distribution List (즉시통보, 실시간) - 이게 진짜 타깃
# - bulletin@woah.org      : 월간 뉴스레터 (실시간 아님) - 제외
WOAH_SENDER_QUERY = "from:woah-info-web@woah.org"

# 회사가 실제 거래 중인 원산지 - 겹치면 긴급 플래그
# ⚠️ WOAH 메일 제목은 국가명을 ISO 3166-1 alpha-3 코드로 표기함(스페인=ESP, 브라질=BRA 등),
#    "spain"/"brazil" 같은 영단어로는 절대 안 걸림 — 코드 기준으로 매칭해야 함.
WATCH_COUNTRY_CODES = {
    "ESP": "스페인",
    "BRA": "브라질",
}

# 제목의 "{ISO3} {DD/MM/YY} — {영어}/{불어}/{스페인어}" 패턴 파싱용
SUBJECT_RE = re.compile(
    r"^\s*([A-Z]{2,3})\s+(\d{2}/\d{2}/\d{2})\s*[—\-–]\s*(.+)$"
)

# ISO 3166-1 alpha-3 코드 → 한글 국가명 (WOAH 회원국 커버용, pycountry 목록 기준)
COUNTRY_KR = {
    "ABW": "아루바", "AFG": "아프가니스탄", "AGO": "앙골라", "AIA": "앵귈라",
    "ALA": "올란드 제도", "ALB": "알바니아", "AND": "안도라", "ARE": "아랍에미리트",
    "ARG": "아르헨티나", "ARM": "아르메니아", "ASM": "아메리칸사모아", "ATA": "남극",
    "ATF": "프랑스령 남방·남극 지역", "ATG": "앤티가바부다", "AUS": "호주", "AUT": "오스트리아",
    "AZE": "아제르바이잔", "BDI": "부룬디", "BEL": "벨기에", "BEN": "베냉",
    "BES": "보네르·신트외스타티위스·사바", "BFA": "부르키나파소", "BGD": "방글라데시",
    "BGR": "불가리아", "BHR": "바레인", "BHS": "바하마", "BIH": "보스니아헤르체고비나",
    "BLM": "생바르텔레미", "BLR": "벨라루스", "BLZ": "벨리즈", "BMU": "버뮤다",
    "BOL": "볼리비아", "BRA": "브라질", "BRB": "바베이도스", "BRN": "브루나이",
    "BTN": "부탄", "BVT": "부베섬", "BWA": "보츠와나", "CAF": "중앙아프리카공화국",
    "CAN": "캐나다", "CCK": "코코스제도", "CHE": "스위스", "CHL": "칠레",
    "CHN": "중국", "CIV": "코트디부아르", "CMR": "카메룬",
    "COD": "콩고민주공화국", "COG": "콩고공화국", "COK": "쿡제도", "COL": "콜롬비아",
    "COM": "코모로", "CPV": "카보베르데", "CRI": "코스타리카", "CUB": "쿠바",
    "CUW": "퀴라소", "CXR": "크리스마스섬", "CYM": "케이맨제도", "CYP": "키프로스",
    "CZE": "체코", "DEU": "독일", "DJI": "지부티", "DMA": "도미니카",
    "DNK": "덴마크", "DOM": "도미니카공화국", "DZA": "알제리", "ECU": "에콰도르",
    "EGY": "이집트", "ERI": "에리트레아", "ESH": "서사하라", "ESP": "스페인",
    "EST": "에스토니아", "ETH": "에티오피아", "FIN": "핀란드", "FJI": "피지",
    "FLK": "포클랜드제도", "FRA": "프랑스", "FRO": "페로제도", "FSM": "미크로네시아",
    "GAB": "가봉", "GBR": "영국", "GEO": "조지아", "GGY": "건지",
    "GHA": "가나", "GIB": "지브롤터", "GIN": "기니", "GLP": "과들루프",
    "GMB": "감비아", "GNB": "기니비사우", "GNQ": "적도기니", "GRC": "그리스",
    "GRD": "그레나다", "GRL": "그린란드", "GTM": "과테말라", "GUF": "프랑스령기아나",
    "GUM": "괌", "GUY": "가이아나", "HKG": "홍콩", "HMD": "허드맥도널드제도",
    "HND": "온두라스", "HRV": "크로아티아", "HTI": "아이티", "HUN": "헝가리",
    "IDN": "인도네시아", "IMN": "맨섬", "IND": "인도", "IOT": "영국령인도양지역",
    "IRL": "아일랜드", "IRN": "이란", "IRQ": "이라크", "ISL": "아이슬란드",
    "ISR": "이스라엘", "ITA": "이탈리아", "JAM": "자메이카", "JEY": "저지",
    "JOR": "요르단", "JPN": "일본", "KAZ": "카자흐스탄", "KEN": "케냐",
    "KGZ": "키르기스스탄", "KHM": "캄보디아", "KIR": "키리바시",
    "KNA": "세인트키츠네비스", "KOR": "대한민국", "KWT": "쿠웨이트", "LAO": "라오스",
    "LBN": "레바논", "LBR": "라이베리아", "LBY": "리비아", "LCA": "세인트루시아",
    "LIE": "리히텐슈타인", "LKA": "스리랑카", "LSO": "레소토", "LTU": "리투아니아",
    "LUX": "룩셈부르크", "LVA": "라트비아", "MAC": "마카오", "MAF": "생마르탱",
    "MAR": "모로코", "MCO": "모나코", "MDA": "몰도바", "MDG": "마다가스카르",
    "MDV": "몰디브", "MEX": "멕시코", "MHL": "마셜제도", "MKD": "북마케도니아",
    "MLI": "말리", "MLT": "몰타", "MMR": "미얀마", "MNE": "몬테네그로",
    "MNG": "몽골", "MNP": "북마리아나제도", "MOZ": "모잠비크", "MRT": "모리타니",
    "MSR": "몬트세랫", "MTQ": "마르티니크", "MUS": "모리셔스", "MWI": "말라위",
    "MYS": "말레이시아", "MYT": "마요트", "NAM": "나미비아", "NCL": "누벨칼레도니",
    "NER": "니제르", "NFK": "노퍽섬", "NGA": "나이지리아", "NIC": "니카라과",
    "NIU": "니우에", "NLD": "네덜란드", "NOR": "노르웨이", "NPL": "네팔",
    "NRU": "나우루", "NZL": "뉴질랜드", "OMN": "오만", "PAK": "파키스탄",
    "PAN": "파나마", "PCN": "핏케언제도", "PER": "페루", "PHL": "필리핀",
    "PLW": "팔라우", "PNG": "파푸아뉴기니", "POL": "폴란드", "PRI": "푸에르토리코",
    "PRK": "북한", "PRT": "포르투갈", "PRY": "파라과이", "PSE": "팔레스타인",
    "PYF": "프랑스령폴리네시아", "QAT": "카타르", "REU": "레위니옹", "ROU": "루마니아",
    "RUS": "러시아", "RWA": "르완다", "SAU": "사우디아라비아", "SDN": "수단",
    "SEN": "세네갈", "SGP": "싱가포르", "SGS": "사우스조지아사우스샌드위치제도",
    "SHN": "세인트헬레나", "SJM": "스발바르얀마옌제도", "SLB": "솔로몬제도",
    "SLE": "시에라리온", "SLV": "엘살바도르", "SMR": "산마리노", "SOM": "소말리아",
    "SPM": "생피에르미클롱", "SRB": "세르비아", "SSD": "남수단", "STP": "상투메프린시페",
    "SUR": "수리남", "SVK": "슬로바키아", "SVN": "슬로베니아", "SWE": "스웨덴",
    "SWZ": "에스와티니", "SXM": "신트마르턴", "SYC": "세이셸", "SYR": "시리아",
    "TCA": "터크스케이커스제도", "TCD": "차드", "TGO": "토고", "THA": "태국",
    "TJK": "타지키스탄", "TKL": "토켈라우", "TKM": "투르크메니스탄", "TLS": "동티모르",
    "TON": "통가", "TTO": "트리니다드토바고", "TUN": "튀니지", "TUR": "튀르키예",
    "TUV": "투발루", "TWN": "대만", "TZA": "탄자니아", "UGA": "우간다",
    "UKR": "우크라이나", "UMI": "미국령군소제도", "URY": "우루과이", "USA": "미국",
    "UZB": "우즈베키스탄", "VAT": "바티칸", "VCT": "세인트빈센트그레나딘",
    "VEN": "베네수엘라", "VGB": "영국령버진아일랜드", "VIR": "미국령버진아일랜드",
    "VNM": "베트남", "VUT": "바누아투", "WLF": "왈리스푸투나", "WSM": "사모아",
    "YEM": "예멘", "ZAF": "남아프리카공화국", "ZMB": "잠비아", "ZWE": "짐바브웨",
}

# 영어 질병명(소문자, 구두점 제거 정규화) → 한글. WOAH 제목의 "/" 첫 구간(영어)을 이 키로 매칭.
# 못 찾으면 영어 원문을 그대로 보여줌(번역 누락을 조용히 숨기지 않기 위함).
DISEASE_KR = {
    "african swine fever": "아프리카돼지열병",
    "classical swine fever": "돼지콜레라(고전적돼지열병)",
    "foot and mouth disease": "구제역",
    "highly pathogenic avian influenza": "고병원성 조류인플루엔자",
    "high pathogenic avian influenza": "고병원성 조류인플루엔자",
    "high pathogenic influenza a poultry": "고병원성 인플루엔자 A(가금)",
    "high pathogenic influenza a non poultry": "고병원성 인플루엔자 A(비가금)",
    "low pathogenic avian influenza": "저병원성 조류인플루엔자",
    "newcastle disease": "뉴캐슬병",
    "west nile fever": "웨스트나일열",
    "bluetongue": "블루텅병",
    "lumpy skin disease": "럼피스킨병",
    "peste des petits ruminants": "소반추수역(PPR)",
    "rift valley fever": "리프트밸리열",
    "rabies": "광견병",
    "anthrax": "탄저병",
    "brucellosis": "브루셀라병",
    "bovine spongiform encephalopathy": "소해면상뇌증(광우병)",
    "bovine tuberculosis": "소결핵병",
    "contagious bovine pleuropneumonia": "우폐역",
    "contagious caprine pleuropneumonia": "산양전염성흉막폐렴",
    "sheep pox and goat pox": "양두·산양두",
    "equine infectious anemia": "마전염성빈혈",
    "equine influenza": "마인플루엔자",
    "african horse sickness": "아프리카마역",
    "glanders": "비저",
    "infectious bovine rhinotracheitis": "전염성소비기관염",
    "trichinellosis": "선모충증",
    "q fever": "큐열",
    "echinococcosis": "포충증",
    "screwworm": "스크루웜(파리유충증)",
    "vesicular stomatitis": "수포성구내염",
    "epizootic haemorrhagic disease": "유행성출혈병",
}


def _normalize(s: str) -> str:
    """구두점·하이픈 유무에 상관없이 매칭되도록 영숫자만 남기고 공백으로 정규화."""
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip().lower()
    return re.sub(r"\s+", " ", s)


_DISEASE_KR_NORM = {_normalize(k): v for k, v in DISEASE_KR.items()}


def translate_disease(en_name: str) -> str:
    """영어 질병명을 정규화해서 DISEASE_KR에서 찾음. 못 찾으면 원문(영어) 그대로 반환
    (조용히 숨기지 않고 번역이 안 됐다는 걸 알 수 있게)."""
    key = _normalize(en_name)
    if key in _DISEASE_KR_NORM:
        return _DISEASE_KR_NORM[key]
    return en_name.strip()




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


def parse_alert(subject: str, body: str):
    """제목에서 국가코드·질병명·통보일자를 추출해 한글로 번역.
    "{ISO3} {DD/MM/YY} — {영어}/{불어}/{스페인어}" 형식이 아니면(구독확인 메일 등
    실제 질병 통보가 아닌 시스템 메일) None을 반환해서 alerts 목록에서 제외시킨다."""
    m = SUBJECT_RE.match(subject.strip())
    if not m:
        return None

    country_code, date_str, disease_part = m.group(1), m.group(2), m.group(3)
    langs = [s.strip() for s in disease_part.split("/")]
    disease_en = langs[0] if langs else disease_part.strip()
    disease_kr = translate_disease(disease_en)

    country_kr = COUNTRY_KR.get(country_code, country_code)
    watch_kr = WATCH_COUNTRY_CODES.get(country_code)

    return {
        "country_code": country_code,
        "country_kr": country_kr,
        "report_date": date_str,  # WOAH 표기 그대로 DD/MM/YY
        "disease_en": disease_en,
        "disease_kr": disease_kr,
        "matched_country": watch_kr,
        "urgent": watch_kr is not None,
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
        if parsed is None:
            print(f"스킵(질병 통보 형식 아님, 구독확인 등 시스템 메일로 판단): {subject}")
            continue
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
