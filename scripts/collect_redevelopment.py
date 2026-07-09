"""
재개발/재건축 관리처분계획인가 소식 수집 스크립트 (뉴스 기반 규칙 추출)

재개발닷컴 같은 상업적 데이터베이스 사이트는 크롤링하지 않고,
"관리처분계획인가"는 지자체가 공식 고시하는 법적 절차이므로 뉴스 검색으로 추적한다.

필요한 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""

import os
import re
import json
import re_common as common

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "redevelopment.json")
LOOKBACK_DAYS = 2

NAVER_KEYWORDS = [
    "관리처분계획인가",
    "관리처분인가",
    "재개발 관리처분",
    "재건축 관리처분",
]

GOOGLE_QUERIES = [
    "관리처분계획인가",
    "재개발 관리처분인가",
    "재건축 관리처분인가",
]

RSS_FEEDS = []

ZONE_PATTERN = re.compile(r"([가-힣0-9]{2,15}(?:구역|지구|재개발|재건축))")


def extract_zone_name(text: str):
    m = ZONE_PATTERN.search(text)
    return m.group(1) if m else None


def process_news(raw_news: list) -> list:
    results = []
    for item in raw_news:
        combined = f"{item['title']} {item['description']}"
        zone = extract_zone_name(combined)
        if not zone:
            continue
        results.append(
            {
                "zone_name": zone,
                "region": common.extract_region(combined) or "확인 필요",
                "stage": "관리처분계획인가",
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
    print(f"[정보] 관리처분인가 소식 추출: {len(extracted)}건")

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
