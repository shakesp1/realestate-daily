"""
향후 개발이 예상되는 지역 소식 수집 스크립트 (뉴스 기반 규칙 추출)

필요한 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""

import os
import json
import re_common as common

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "development_areas.json")
LOOKBACK_DAYS = 2

NAVER_KEYWORDS = [
    "신도시 개발계획",
    "산업단지 조성",
    "역세권 개발",
    "GTX 정차역",
    "국가산단 지정",
    "3기 신도시",
]

GOOGLE_QUERIES = [
    "신도시 개발계획 발표",
    "GTX 정차역 확정",
    "산업단지 조성 계획",
]

RSS_FEEDS = []

DEV_TYPE_KEYWORDS = [
    ("신도시", ["신도시"]),
    ("교통망(GTX 등)", ["GTX", "역세권", "정차역", "철도", "지하철 연장"]),
    ("산업단지", ["산업단지", "국가산단", "일반산단"]),
    ("공공택지", ["공공택지", "공공주택지구"]),
]


def extract_dev_type(text: str) -> str:
    for label, keywords in DEV_TYPE_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return label
    return "기타개발"


def process_news(raw_news: list) -> list:
    results = []
    for item in raw_news:
        combined = f"{item['title']} {item['description']}"
        region = common.extract_region(combined)
        if not region:
            continue
        results.append(
            {
                "region": region,
                "dev_type": extract_dev_type(combined),
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
    print(f"[정보] 개발 예상지역 소식 추출: {len(extracted)}건")

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
