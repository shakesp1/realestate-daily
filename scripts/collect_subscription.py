"""
청약 관련 일정 수집 스크립트 (뉴스 기반 규칙 추출)

필요한 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""

import os
import re
import json
import re_common as common

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "subscription.json")
LOOKBACK_DAYS = 2

NAVER_KEYWORDS = [
    "아파트 청약 일정",
    "분양 청약 접수",
    "특별공급 청약",
    "무순위 청약",
    "청약 당첨자 발표",
]

GOOGLE_QUERIES = [
    "아파트 청약 일정",
    "분양 청약 접수",
    "특별공급 청약",
]

RSS_FEEDS = []


def extract_housing_name(title: str):
    # "OOO, ~~" 또는 "OOO 청약" 형태에서 주택명(단지명) 추출
    m = re.match(r"^([가-힣A-Za-z0-9&·\s]{2,20}?)\s*[,·]", title)
    if m:
        return m.group(1).strip()
    m = re.search(r"([가-힣A-Za-z0-9&]{2,20}(?:아파트|자이|푸르지오|힐스테이트|더샵|SK뷰|롯데캐슬|IPARK|아이파크|위브|포레온))", title)
    if m:
        return m.group(1)
    return None


def process_news(raw_news: list) -> list:
    results = []
    for item in raw_news:
        combined = f"{item['title']} {item['description']}"
        housing_name = extract_housing_name(item["title"])
        if not housing_name:
            continue
        results.append(
            {
                "housing_name": housing_name,
                "region": common.extract_region(combined) or "확인 필요",
                "summary": common.build_summary(item["title"], item["description"]),
                "source_url": item["link"],
                "pub_date": item["pub_date"],
            }
        )
    return results


def load_existing() -> list:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def dedup_key(entry: dict) -> str:
    return entry["source_url"]


def main():
    common.check_required_env()

    raw_news = common.collect_raw_news(NAVER_KEYWORDS, GOOGLE_QUERIES, RSS_FEEDS, LOOKBACK_DAYS)
    extracted = process_news(raw_news)
    print(f"[정보] 청약 일정 추출: {len(extracted)}건")

    existing = load_existing()
    existing_keys = {dedup_key(e) for e in existing}

    new_entries = [e for e in extracted if dedup_key(e) not in existing_keys]
    print(f"[정보] 신규 항목 (중복 제외): {len(new_entries)}")

    combined = existing + new_entries
    combined.sort(key=lambda e: e["pub_date"], reverse=True)

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"[완료] 총 {len(combined)}건 저장 -> {DATA_PATH}")


if __name__ == "__main__":
    main()
